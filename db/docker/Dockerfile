FROM postgres:latest

ENV POSTGRES_HOST_AUTH_METHOD=trust
COPY db/init.sql /docker-entrypoint-initdb.d/1.sql
COPY db/mockData.sql /docker-entrypoint-initdb.d/2.sql

EXPOSE 5432