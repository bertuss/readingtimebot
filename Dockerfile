FROM python:3.7-stretch

WORKDIR /app

COPY src/requirements.txt requirements.txt

RUN pip install -U pip && \
    pip wheel -r requirements.txt

COPY src /app
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["python", "-u", "/app/bot.py"]