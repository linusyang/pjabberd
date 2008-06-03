#!/bin/bash

markdown design.md > design.html && ./wrap-html.py design.html > tmp.html && mv tmp.html design.html
