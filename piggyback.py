#!/usr/bin/env python3

import sys
import base64
import ssl
import socket
import select
import fcntl
import os
import argparse
import re
import subprocess

VERSION="1.0.1"

def piggyback(proxy_host, proxy_port, target_host, target_port, auth):
    """
    the piggyback main loop. connects and authenticates with the proxy, then begins piping data

    proxy_host -- the hostname of the proxy
    proxy_port -- the port on the proxy host to connect. this is expected to be https.
    target_host -- the hostname to connect to downstream of the proxy (see %h from ProxyCommand)
    target_port -- the port to connect to on the downstream host (see %p from ProxyCommand)
    auth -- a tuple (username, password) for the proxy authentication
    """
    (auth_user, auth_pass) = auth

    with socket.socket() as tcp:
        with ssl.wrap_socket(tcp) as tls:
            tls.connect((proxy_host, proxy_port))
            tls.setblocking(False)
            set_nonblocking_stdin()

            b64_auth = base64.standard_b64encode(f"{auth_user}:{auth_pass}".encode()).decode()
            request = f"CONNECT {target_host}:{target_port} HTTP/1.0\r\nProxy-Authorization: Basic {b64_auth}\r\n\r\n"
            tls.sendall(request.encode())

            # mutable state used inside the main loop
            is_connected = False
            stdin_buffer = None
            tls_buffer = None

            while True:
                if not is_connected:
                    (read_ready, _, _) = select.select([tls], [], [], 1)

                    if tls in read_ready:
                        response = tls.read().decode()
                        response_status = response.splitlines()[0]
                        eprint(response_status)

                        if "200" not in response_status:
                            exit(-1)
                        else:
                            is_connected = True

                else:
                    (read_ready, _, _) = select.select([tls, sys.stdin], [], [], 1)

                    if tls in read_ready:
                        try:
                            # handle reading the TLS socket, and writing its contents to stdout
                            if not tls_buffer:
                                tls_buffer = tls.recv(4096)
                            sys.stdout.buffer.write(tls_buffer)
                            sys.stdout.buffer.flush()
                            tls_buffer = None
                        except ssl.SSLWantReadError:
                            # the socket may be ready to read, but the protocol might not be. try reading into the buffer again.
                            continue

                    if sys.stdin in read_ready:
                        try:
                            # handle reading stdin, and writing its contents to the TLS socket
                            if not stdin_buffer:
                                stdin_buffer = sys.stdin.buffer.read(4096)
                            tls.sendall(stdin_buffer)
                            stdin_buffer = None
                        except ssl.SSLWantWriteError:
                            # the socket may be ready to write, but the protocol might not be. try writing the buffer again.
                            continue


def set_nonblocking_stdin():
    """
    puts stdin into non-blocking mode
    """
    stdin = sys.stdin.fileno()
    flags = fcntl.fcntl(stdin, fcntl.F_GETFL)
    fcntl.fcntl(stdin, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def read_file_auth(auth_file):
    """
    reads username and password credentials from the specified file. the file format is:
    - clear text (you should consider using your keychain)
    - username:password
    """
    with open(auth_file) as file:
        parts = file.readline().strip().split(":", 2)
        return (parts[0], parts[1])


def read_keychain_auth(password_name):
    """
    reads username and password credentials from your macos keychain, under the name specified by the password_name parameter
    """
    generic_password_output = subprocess.check_output([
        '/usr/bin/security',
        'find-generic-password',
        '-s',
        password_name
    ], stderr=subprocess.PIPE).decode('utf-8')

    account = ''
    for line in generic_password_output.splitlines():
        match = re.match('^\s+"acct"<\w+>="(.+)"\s*$', line)
        if match:
            account = match.group(1)

    password = subprocess.check_output([
        '/usr/bin/security',
        'find-generic-password',
        '-w',
        '-s',
        password_name
    ], stderr=subprocess.PIPE).decode('utf-8').strip()

    return (account, password)

def setup():
    from string import Template

    def query(prompt, default):
        i = input(f"{prompt} [{default}]: ")
        if len(i.strip()) == 0:
            return default
        return i

    piggyback_exe = query("piggyback", os.path.abspath(__file__))
    squid_hostname = query("squid host", "squid")
    squid_port = query("squid port", "443")
    filename = query("ssh config file", f"{os.environ['HOME']}/.ssh/piggyback")

    template = Template("""
Host *
    SendEnv LANG LC_*
    ServerAliveInterval 30
    StrictHostKeyChecking no
    ProxyCommand $piggyback_exe $squid_hostname $squid_port %h %p
    ServerAliveInterval 60
    """.strip())

    with open(filename, "w") as f:
        f.write(template.substitute(locals()))
    
    print(f"created: {filename}")
    print(f"""
!! Create your credentials in your keychain !!:
1: Open "Keychain Access"
2: Select your login keychain
3: Select "passwords"
4: Click the "+" to add a new password
    Keychain Item Name: piggyback
    Account Name:       <your proxy username>
    Password:           <your proxy password>
5: Click "Add"

Run SSH: ssh -f {filename} <args>
    """)

def eprint(*args, **kwargs):
    """
    prints to stderr
    """
    print(*args, file=sys.stderr, **kwargs)

def main():
    if any(a in {"--setup", "--config"} for a in sys.argv):
        setup()
    else:
        parser = argparse.ArgumentParser(description=f"piggyback v{VERSION}")
        parser.add_argument("proxy_host")
        parser.add_argument("proxy_port", type=int)
        parser.add_argument("target_host")
        parser.add_argument("target_port", type=int)

        parser.add_argument("-a", "--auth", default="keychain", choices=["keychain", "file"], help="which credentials mechanism to use")
        parser.add_argument("-k", "--keychain", default="piggyback", help="the name of the password entry in your keychain")
        parser.add_argument("-f", "--auth-file", help="the path to a file which contains: <user>:<password>")
        args = parser.parse_args()

        if args.auth == "keychain":
            auth = read_keychain_auth(args.keychain)
        elif args.auth == "file":
            auth = read_file_auth(args.auth_file)

        piggyback(args.proxy_host, args.proxy_port, args.target_host, args.target_port, auth)


if __name__ == "__main__":
    main()
    