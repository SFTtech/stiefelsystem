.PHONY: all
all: setup-link

.PHONY: clean
clean:
	rm setup-link

.PHONY: run
run: setup-link
	strace ./setup-link 00:e0:4c:69:89:37 lolif

setup-link: setup-link.c Makefile
	clang -o setup-link setup-link.c -ludev -O3 -std=gnu11 -Wall -Wextra -pedantic
