# Security Policy

## Reporting a Vulnerability

This is a private repository for an internal calibration management tool
built for Instruworks LLC FZ. If you find a security issue (e.g. an auth
bypass, a way to access another user's calibration data, or exposed
credentials), please report it directly and privately to the project's
Architecture Lead or the supervising engineer at Instruworks LLC FZ
rather than opening a public issue.

Please include:
- A description of the issue and its potential impact
- Steps to reproduce it, if possible
- Which endpoint(s) or file(s) are affected

## Scope

This project handles calibration records for a ISO/IEC 17025:2017
accredited lab. Anything that could expose one user's session data to
another user, bypass authentication, or allow unauthorized data
modification is considered high priority.

## Supported Versions

This project does not currently maintain multiple released versions -
only the latest code on the `main` branch is supported.
