# piggyback

TLS on TLS!

This tool allows you to tunnel SSH (using `ProxyCommand`) via HTTPS (with [Squid Proxy](http://www.squid-cache.org)). It is a python implementation of [`corkscrew`](https://github.com/bryanpkc/corkscrew), but over https (TLS) instead of http (plaintext). 

## Why should I use this?

- If you've been using `corkscrew`, it transmits your proxy authentication credentials in the clear over regular http.
- This tool uses the built in `ProxyCommand` protocol that `ssh` supports, giving you full access to `ssh` and `scp` without wrappers.

## Easy Installation

1. `brew tap nike-inc/nike`
1. `brew install piggyback`
1. `piggyback --config`
1. Follow the prompts and instructions!

## Prerequisites

- Python 3: `brew install python3`

## Usage

Like `corkscrew`, `piggyback.py` is a ssh ProxyCommand compatible program. It:

- establishes a TCP session with the squid proxy
- establishes an HTTPS session with the squid proxy with your credentials
- pipes stdin → https, and https → stdout (per the ProxyCommand protocol)

### Authentication Info

1. Create a keychain password to contain your username and credentials
    1. Open `Keychain Access`
    1. Select your *login* keychain
    1. Select *Passwords*
    1. Click the *+* button at the bottom of the screen 
2. Name the entry `piggyback`
3. For `Account Name` use your NT account

### Configuration

These instructions are for creating a stand-alone configuration file that you select on each invokation of `ssh`. You could
get fancy with host selection in your global `ssh` config, but AWS's ip ranges don't make that easy.

1. Create a file for your configuration: `touch ~/.ssh/piggyback`
2. Edit that file with content similar to:
```
Host *
  SendEnv LANG LC_*
  ServerAliveInterval 30
  StrictHostKeyChecking no
  ProxyCommand /path/to/piggyback.py squid.domain.com 443 %h %p
  ServerAliveInterval 60
```
3. Make sure to edit your actual `/path/to/piggyback.py`
4. Invoke `ssh` with the `-F ~/.ssh/piggyback` flag to make ssh read that configuration file.

### Ad-Hoc Configuration

`ssh` allows you to pass in options on the command line with the `-o` flag. The content is the same as you'd have in your configuration file.

Here's an example:

```
ssh -A -o "ProxyCommand ./piggyback.py squid.domain.com 443 %h %p" 10.11.12.13
```

### Additional Credentials Support

* Get credentials from a file: `--auth file -f /path/to/file`
* Create keychain passwords with different names: `--auth keychain -k some_other_name`

## Tips

### Tip: Send all SSH traffic through piggyback

To avoid having to pass `-F ~/.ssh/piggyback` all of the time you can make
piggyback your default SSH configuration.

1. Make it default `mv ~/.ssh/piggyback ~/.ssh/config`
2. If there is a host wildcard, you will need to add host exceptions where
needed e.g. `!github.com` in this example:
```
Host * !github.com
    SendEnv LANG LC_*
    ServerAliveInterval 30
    StrictHostKeyChecking no
    ProxyCommand /usr/local/bin/piggyback squid.example.com 443 %h %p
    ServerAliveInterval 60
```

### Tip: Learn general SSH config

The piggyback configuration file is just an SSH configuration file.  You can
use any configuration options normally available (e.g. `man ssh_config`).
For example, if you use a different user name on your servers than locally,
you can set the default user in `~/.ssh/piggyback`. E.g. add `User kermit` in:

```
Host *
    User kermit
    SendEnv LANG LC_*
    ServerAliveInterval 30
    StrictHostKeyChecking no
    ProxyCommand /usr/local/bin/piggyback squid.example.com 443 %h %p
    ServerAliveInterval 60
```

Another option is to add the `IdentityFile` directive, e.g. you might copy
`~/.ssh/piggyback` to `~/.ssh/dev`, add the line
`IdentityFile ~/.ssh/dev-private-key.pem`, and then ssh with
`ssh -F ~/.ssh/dev <ip-address>` rather than
`ssh -F ~/.ssh/piggyback -i ~/.ssh/dev-private-key.pem <ip-address>`.

## Security Considerations

* Don't enable insecure versions of TLS on your hosts!
* https://docs.python.org/2/library/ssl.html#ssl-security
