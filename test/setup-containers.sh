#!/bin/bash

set -ex

# change to the directory containing this script
cd "$( dirname "${BASH_SOURCE[0]}" )"

# fetch the latest version of each base image
# without this step the build phase will use cached (old) versions of the base containers
for image in 'ubuntu:jammy' 'ubuntu:noble' 'amazonlinux:2023'; do
    docker pull ${image}
done

for image in 'jammy' 'noble' 'amazon-linux2023' 'amazon-linux2023-py311'; do
    docker build -t wheel-tester/${image} -f docker/Dockerfile.${image} .
done

image=testhost
docker build -t wheel-tester/${image} -f docker/Dockerfile.${image} \
           --build-arg USER_GID="$(id -g)" \
           --build-arg USER_UID="$(id -u)" \
           --build-arg USER_NAME="$(whoami)" \
           --build-arg DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
           .
#docker image prune -y
