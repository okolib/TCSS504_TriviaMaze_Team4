FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

RUN git clone -b main https://github.com/okolib/TCSS504_TriviaMaze_Team4.git /app

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
