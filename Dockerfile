FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt /app

RUN apk add --no-cache gcc python3-dev musl-dev linux-headers curl

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8080

HEALTHCHECK --interval=1m --start-period=5s --timeout=10s CMD curl --fail -m 10 http://localhost:8080 || exit 1

CMD ["python", "App.py"]