FROM python:3.12-slim
COPY hbbs hbbr /usr/local/bin/
COPY painel/painel.py /usr/local/bin/painel.py
WORKDIR /root
EXPOSE 21115 21116 21116/udp 21117 21118 21119 8090
CMD ["hbbs"]
