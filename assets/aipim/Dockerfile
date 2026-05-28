# syntax=docker/dockerfile:1.6
#
# ai-pim-utils runtime image.
#
# Why Ubuntu 24.04 base: ships glibc 2.39, which satisfies the >=2.34
# requirement of the prebuilt CLIs. The host (Ubuntu 20.04 / glibc 2.31)
# cannot run them directly.
#
# Why install to /opt/ai-pim: the runtime container bind-mounts the host
# $HOME so the user's tokens/config persist. If install.sh wrote to
# $HOME/.local/bin inside the image, that path would be shadowed by the
# bind-mount and the binaries would vanish at runtime.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        less \
        libpcsclite1 \
        openssh-client \
        tzdata \
        vim-tiny \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install ai-pim-utils CLIs to /opt/ai-pim. HOME is scoped to this RUN only,
# so the final image does not carry HOME= and the runtime user's HOME is
# honored at exec time.
RUN mkdir -p /opt/ai-pim \
 && HOME=/opt/ai-pim bash -c '\
        curl -fsSL https://outlook-cli-80d21a.gitlab-master-pages.nvidia.com/install.sh -o /tmp/install.sh \
     && bash /tmp/install.sh \
     && rm /tmp/install.sh'

ENV PATH=/opt/ai-pim/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
