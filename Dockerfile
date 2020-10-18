FROM python:3.8
RUN pip install bottle
COPY . .
CMD python csv-to-rest.py
