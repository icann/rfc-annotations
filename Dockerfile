FROM python:3.11-rc-alpine

LABEL maintainer="martin.boettcher@greenbytes.de"
LABEL name="Python tool for analysing DNS RFC security issues"
LABEL description="Python based tool for analyzing DNS RFC security issues"
LABEL version="0.0.35" release="35"

RUN apk add rsync

WORKDIR /
COPY *.html rfcs-to-use.txt errata.patch program/* /

CMD ["python3", "-u", "main.py"]