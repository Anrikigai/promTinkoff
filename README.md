# promTinkoff

Экспортирует данные из Тинькофф Инвестиции в Prometheus для использования в Grafana.  

## Запуск

### Переменные окружения

* TINVEST_TOKEN - токен Тинькофф Инвестиции (обязательный параметр).  
Получить: https://tinkoffcreditsystems.github.io/invest-openapi/auth/
* LISTEN_PORT - по умолчанию TCP/8848
* UPDATE_PERIOD - как часто обновляет данные от Тинькофф Инвестиции (по умолчанию 600 сек)

### Python

```
TINVEST_TOKEN=<TOKEN> ./promTinkoff.py
```

Либо `./promTinkoff.sh`, в котором данный скрипт вызывается в бесконечном цикле для рестарта в случае аварийного завершения.

### Docker

```
docker run --detach --name promTinkoff \
    -e "TINVEST_TOKEN=$TINVEST_TOKEN" \
    --memory=64M --cpus="0.1" \
    --restart=unless-stopped anrikigai/promtinkoff
```

Сборка  
`docker build -t anrikigai/promtinkoff .`

## Формируемые данные

#### tcs_item

Для удобства отображения данные по каждой позиции экспортируются в трех валютах: EUR, USD, RUB (`balance_currency`).  
При этом `currency` получается от Tinkoff. Скажем, для "Тинькофф Вечный портфель EUR" `currency=EUR`, для Pfizer - `currency=USD`.  
```
tcs_item{account="Tinkoff", balance_currency="EUR", currency="EUR", instance="promTinkoff:8848", job="tinkoff", name="Тинькофф Вечный портфель EUR", ticker="TEUR", type="Etf"}

tcs_item{account="Tinkoff", balance_currency="USD", currency="EUR", instance="promTinkoff:8848", job="tinkoff", name="Тинькофф Вечный портфель EUR", ticker="TEUR", type="Etf"}

tcs_item{account="Tinkoff", balance_currency="RUB", currency="EUR", instance="promTinkoff:8848", job="tinkoff", name="Тинькофф Вечный портфель EUR", ticker="TEUR", type="Etf"}

tcs_item{account="Tinkoff", balance_currency="RUB", currency="USD", instance="promTinkoff:8848", job="tinkoff", name="Pfizer", ticker="PFE", type="Stock"}
```

Это можно использовать для оценки диверсификации по валютам.  Поэтому для позиций кеша в евро и долларе принудительно устанавливается соответствующая валюта, хотя Тинькофф и возвращает для них RUB.  

Впрочем, в реальности это скорее "в какой валюте покупалось", а не валюта актива. Например, фонд "Гособлигации США с защитой от инфляции" торгуется за рубли, и для него возвращается `currency=RUB` (увы).   
```
tcs_item{account="TinkoffIis", balance_currency="RUB", currency="RUB", instance="promTinkoff:8848", job="tinkoff", name="FinEx Облигации TIPS", ticker="FXTP", type="Etf"}
```

Так что со специализированными пакетами такой вариант не конкурирует :)


### tcs_yield

Аналогичный подход с дублированием в трех валюьтах используется для оценки прибыли/убытков.
```
tcs_yield{account="Tinkoff", balance_currency="EUR", currency="USD", instance="promTinkoff:8848", job="tinkoff", name="Pfizer", ticker="PFE", type="Stock"} 90.99262579525735

tcs_yield{account="Tinkoff", balance_currency="USD", currency="USD", instance="promTinkoff:8848", job="tinkoff", name="Pfizer", ticker="PFE", type="Stock"} 107.5

tcs_yield{account="Tinkoff", balance_currency="RUB", currency="USD", instance="promTinkoff:8848", job="tinkoff", name="Pfizer", ticker="PFE", type="Stock"} 7866.3125
```


### tcs_rate

Для конвертации используется курс, получаемый, как последняя сделка из стакана. И сохраняется для трех пар валют.  
```
tcs_rate{currency="EURRUB", instance="promTinkoff:8848", job="tinkoff"} 86.45
tcs_rate{currency="USDRUB", instance="promTinkoff:8848", job="tinkoff"} 73.175
tcs_rate{currency="EURUSD", instance="promTinkoff:8848", job="tinkoff"} 1.1814144174923131
```


### Аккаунты

Помимо вывода данных по каждому аккаунту, получаемого от Тинькофф Инвестиций (в данном случае Tinkoff, TinkoffIis), также добавляются автоматически посчитанные записи для фиктивного аккаунта `_Total_`  
```
tcs_item{account="_Total_", balance_currency="RUB", currency="Multi", instance="promTinkoff:8848", job="tinkoff", name="_Total_", ticker="_Total_", type="_Total_"}

tcs_yield{account="_Total_", balance_currency="RUB", currency="Multi", instance="promTinkoff:8848", job="tinkoff", name="_Total_", ticker="_Total_", type="_Total_"}
```

Это облегчает написание формул в Grafana.

## Prometheus - описание job

```
  - job_name: 'tinkoff'
    scrape_interval: 600s
    static_configs:
      - targets: ['promTinkoff:8848']
```

## Grafana - несколько примеров

Поскольку API возвращает среднюю цену позиции и баланс (количество), их произведение, выводимое в `tcs_item`, является суммой потраченных (инвестированных) средств.  
Для получения текущей стоимости проще всего прибавить ожидаемые прибыли/убытки (`tcs_yield`).  

### Текущее портфолио
```
Sum(tcs_item{balance_currency="RUB",account=~"T.*"}) + Sum(tcs_yield{balance_currency="RUB",account=~"T.*"})

Sum(tcs_item{balance_currency="USD",account=~"T.*"}) + Sum(tcs_yield{balance_currency="USD",account=~"T.*"})

Sum(tcs_item{balance_currency="EUR",account=~"T.*"}) + Sum(tcs_yield{balance_currency="EUR",account=~"T.*"})
```

Фильтр `account=~"T.*"` используется, чтобы исключить фиктивный аккаунт `_Total_` (иначе суммы удвоятся).  
Тот же результат можно получив использовав `tcs_item{balance_currency="RUB",account="_Total_"}) + Sum(tcs_yield{balance_currency="RUB",account="_Total_"})`

### Details

![Details](img/details.png?raw=true)
```
Sum(tcs_item{balance_currency="RUB"}) by (account) + Sum(tcs_yield{balance_currency="RUB"}) by (account)

Sum(tcs_item{balance_currency="USD"}) by (account) + Sum(tcs_yield{balance_currency="USD"}) by (account)

Sum(tcs_item{balance_currency="EUR"}) by (account) + Sum(tcs_yield{balance_currency="EUR"}) by (account)
```

Три строчки для того, чтобы видеть сразу 3 колонки с RUB, USD, EUR.


### Current position and yield - $Item
`$Item` в заговлоке (Title) - не ошибка. Это параметр, выбираемый в моем Dashboard для получения расширенной информации по какому-то инструменту.

![Current position](img/pfizer.png?raw=true)
```
sum(tcs_item{name="$Item",balance_currency="RUB"}) + sum(tcs_yield{name="$Item",balance_currency="RUB"})

Sum(tcs_item{name="$Item",balance_currency="USD"}) + sum(tcs_yield{name="$Item",balance_currency="USD"})

sum(tcs_item{name="$Item",balance_currency="EUR"}) + sum(tcs_yield{name="$Item",balance_currency="EUR"})

sum(tcs_yield{name="$Item",balance_currency="RUB"})

sum(tcs_yield{name="$Item",balance_currency="USD"})

sum(tcs_yield{name="$Item",balance_currency="EUR"})
```

Первые 3 значения - текущая позиция по данному инструменты в трех валютах.  
3 позиции в нижнем ряду  - прибыли/убытки.


### Диверсификация портфеля

![Диверсификация портфеля](img/portfolio_div.png?raw=true)
```
sum(tcs_item{balance_currency="RUB",account=~"T.*", currency="RUB"}) by (type) + sum(tcs_yield{balance_currency="RUB",account=~"T.*", currency="RUB"}) by (type)

sum(tcs_item{balance_currency="RUB",account=~"T.*", currency="USD"}) by (type) + sum(tcs_yield{balance_currency="RUB",account=~"T.*", currency="USD"}) by (type)

sum(tcs_item{balance_currency="RUB",account=~"T.*", currency="EUR"}) by (type) + sum(tcs_yield{balance_currency="RUB",account=~"T.*", currency="EUR"}) by (type)
```

Для каждой из валют результаты дополнительно разбиваются (группируются) по типам инструментов (акции, бонды и т.п.).  
`balance_currency` в данном случае не имеет значения (пропорции одинаковы в любой валюте). Лишь бы была одинакова во всех формулах.

### ETF

![ETF](img/etf.png?raw=true)
```
sum(tcs_item{type="Etf",balance_currency="RUB"}) by (name) + sum(tcs_yield{type="Etf",balance_currency="RUB"}) by (name)
```

Аналогичные графики строятся и для других инструментов (Stock, Bond...).  
К сожалению, нет простого способа отделить ETF на акции от ETF на облигации (бонды). 
