FROM python:3-alpine

EXPOSE 8848
WORKDIR /app

COPY app/* /app/
RUN pip install -i https://test.pypi.org/simple/ --extra-index-url=https://pypi.org/simple/ tinkoff-invest-openapi-client \
    && pip install --no-cache-dir -r requirements.txt

CMD ["sh", "./promTinkoff.sh"]
