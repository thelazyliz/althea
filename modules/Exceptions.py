#! /usr/bin/env python3
# -*- coding: utf-8 -*-

class MissingEnvVar(Exception):
    def __init__(self, msg):
        super(MissingEnvVar, self).__init__(msg)