FROM python:3.11-rc-alpine

LABEL maintainer="martin.boettcher@greenbytes.de"
LABEL name="Python tool for analysing DNS RFC security issues"
LABEL description="Python based tool for analyzing DNS RFC security issues"
LABEL version="0.0.36" release="36"

RUN apk add rsync

WORKDIR /
RUN mkdir default-config
COPY program/* /
COPY default-config/* default-config

CMD ["python3", "-u", "main.py"]