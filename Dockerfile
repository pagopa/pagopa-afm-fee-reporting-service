FROM python:3.11

WORKDIR /app
COPY . /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PYTHONUNBUFFERED=0
CMD ["python", "-u", "src/fee-report-builder.py"]