FROM python:3.10

# Set environment variables for pip
WORKDIR /app

COPY ./dockerfile/requirements.txt ./dockerfile/requirements.txt
# COPY myname.txt myname.txt
COPY ./dockerfile/medhoush_telegram_2.0.0.py ./dockerfile/medhoush_telegram_2.0.0.py
RUN apt-get update && apt-get install git -y
RUN pip3 install  -r ./dockerfile/requirements.txt
COPY . .

CMD python3  ./dockerfile/medhoush_telegram_2.0.0.py