FROM ubuntu:bionic
RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install -y python3 python3-pip
RUN pip3 install bottle
COPY . .
CMD bash -c "python3 csv-to-rest.py"
