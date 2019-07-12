# piggyback change log

## Known Issues

- When using `piggyback` for `scp`, the transfer will get two 100%, then apparently "hang" for several seconds. If you wait, it will finish correctly.

## 1.0.2

- During setup console output suggested using 'ssh -f configfile' vs. 'ssh -F configfile'.

## 1.0.1

- Fixed an issue where tailing logs in an ssh session produced a want-read-error

## 1.0

- Full implementation of `ssh` `ProxyCommand` protocol.
