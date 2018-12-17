# packages do not include gnucash3(python3), python:2 does not install python-gnucash correctly
FROM ubuntu

RUN apt-get update \
 && apt-get install -y \
    python-gnucash \
    python-pip \
    libdbd-mysql \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gnucash_rest gnucash_rest
COPY main.py .
COPY www www

EXPOSE 5000

CMD ["python", "main.py"]
