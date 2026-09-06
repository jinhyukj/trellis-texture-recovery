#!/bin/sh
case "$1" in
  Username*) echo "x-access-token";;
  Password*) cat /workspace/jh/.gh_token;;
esac
