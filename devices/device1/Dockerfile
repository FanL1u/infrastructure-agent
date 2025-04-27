FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    openssh-server \
    net-tools \
    iputils-ping \
    iproute2 \
    curl \
    traceroute \
    tcpdump \
    python3 \
    sudo \
    vim

# Configure SSH
RUN mkdir /var/run/sshd
RUN echo 'root:password' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create a non-root user
RUN useradd -m -s /bin/bash admin
RUN echo 'admin:admin' | chpasswd
RUN usermod -aG sudo admin
RUN echo 'admin ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/admin

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]