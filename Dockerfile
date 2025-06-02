FROM python:3.10

# Set environment variables for pip
WORKDIR /app

COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install git -y
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . /app/

CMD python3  ./medhoush_telegram_2.0.0.py