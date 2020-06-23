.PHONY: all
all: setup-link

.PHONY: clean
clean:
	rm setup-link

.PHONY: run
run: setup-link
	strace ./setup-link 00:e0:4c:69:89:37 lolif

setup-link: setup-link.c Makefile
	gcc -o setup-link -fdata-sections -ffunction-sections setup-link.c -static -O3 -std=gnu11 -Wall -Wextra -pedantic -Wl,--gc-sections,--strip-all -fomit-frame-pointer -flto
