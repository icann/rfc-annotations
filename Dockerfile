#the rsync version available for python:3.x-alpine is currently broken!
FROM python:3.8-slim

LABEL maintainer="martin.boettcher@greenbytes.de"
LABEL name="RFC Annotations Tool"
LABEL description="The RFC annotations tool allows a user to view a set of RFCs with relevant annotations"
LABEL version="0.0.38" release="38"

RUN apt-get update; apt-get install -y rsync
# rc-alpine version: RUN apk add rsync

WORKDIR /
RUN mkdir default-config
COPY program/* /
COPY default-config/* default-config

CMD ["python3", "-u", "main.py"]