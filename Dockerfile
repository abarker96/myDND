# Parent image
FROM mongo:6.0.1

# Modify child mongo to use /data/db2 as dbpath
COPY ./docker/mongodb.conf /etc
RUN mkdir -p /data/db2 \
  && chown -R mongodb:mongodb /data/db2

# Install curl + node
RUN apt-get update \
  && apt-get -y install curl \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
RUN apt-get install -y nodejs \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install Python + pip
RUN apt-get update \
  && apt-get install -y python3 python3-pip \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install python requirements
RUN pip3 install flask pymongo pypdf reportlab


ENV MONGODB_URI=mongodb://localhost:27017/5e-database

# Add code
WORKDIR /data/db2
COPY --chown=mongodb:mongodb package.json package-lock.json /data/db2/
RUN npm install
COPY --chown=mongodb:mongodb . /data/db2/

# Compile TypeScript
RUN npm run build:ts

# Seed DB during build
RUN mongod --fork --logpath /var/log/mongodb.log --dbpath /data/db2 \
  && npm run db:refresh \
  && mongod --dbpath /data/db2 --shutdown \
  && chown -R mongodb:mongodb /data/db2

# Persist DB
VOLUME /data/db2

# Copy your Flask app
WORKDIR /app
COPY app.py /app/app.py
COPY ./res/ /res/
COPY ./templates /app/templates
COPY ./static /app/static

EXPOSE 27017
EXPOSE 5000

HEALTHCHECK CMD curl --connect-timeout 10 --silent --fail http://localhost:27017 || exit 1

# Start Mongo in background AND Flask in foreground
# CMD bash -c "mongod --config /etc/mongodb.conf & python3 /app/app.py"
CMD ["bash", "-c", "python3 /app/app.py & exec docker-entrypoint.sh mongod --config /etc/mongodb.conf"]
