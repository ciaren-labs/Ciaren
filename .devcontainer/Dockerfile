# Base image for the Ciaren dev container / GitHub Codespace.
#
# The python devcontainer image ships a Yarn apt source whose signing key is
# expired, which makes every `apt-get update` (and so every dev container
# feature that installs packages) fail. Ciaren does not use Yarn.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
RUN rm -f /etc/apt/sources.list.d/yarn.list
