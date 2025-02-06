FROM python:3.11@sha256:14b4620f59a90f163dfa6bd252b68743f9a41d494a9fde935f9d7669d98094bb

WORKDIR /app
COPY . /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PYTHONUNBUFFERED=0
CMD ["python", "-u", "src/fee-report-builder.py"]