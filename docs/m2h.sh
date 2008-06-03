#!/bin/bash

# this generates the design.html file from the markdown file
markdown design.md > design.html && ./wrap-html.py design.html > tmp.html && mv tmp.html design.html
