FROM python:3.11@sha256:adb581d8ed80edd03efd4dcad66db115b9ce8de8522b01720b9f3e6146f0884c

WORKDIR /app
COPY . /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PYTHONUNBUFFERED=0
CMD ["python", "-u", "src/fee-report-builder.py"]