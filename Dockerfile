FROM python:3.11

CMD pip install flask requests numpy
RUN python server.py
