/**
 * When an adapter with the given mac address is connected, this tool
 * automatically renames it to the given name, and sets it up.
 *
 * Platform-specific for Linux.
 * Requires no external tools or filesystem structure.
 */
#define _GNU_SOURCE

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <arpa/inet.h>
#include <ifaddrs.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <netinet/ip.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>


// the socket file descriptor that we use for IOCTLs.
// see man 7 netdevice.
int socket_fd;

/**
 * copies an interface name from src to dest.
 *
 * src must be null-terminated or at least 15 bytes long.
 * dest must be at least 16 bytes long. it will have at least
 * one null byte at position 15, and possibly more if the name
 * in src is shorter.
 */
void ifnamcpy(char *dest, const char *src) {
    int pos = 0;
    for (; pos < IFNAMSIZ; pos++) {
        if (src[pos] == '\0' || pos > 15) { break; }
        dest[pos] = src[pos];
    }
    for (; pos < IFNAMSIZ; pos++) {
        dest[pos] = '\0';
    }
}

/**
 * sets the interface up or down.
 * if up == 0, sets it down.
 * otherwise, sets it up.
 * 
 * returns 0 on success,
 * negative number on failure.
 *
 * calls perror() on failure.
 */
int set_if_up(const char *ifname, int up) {
    // the interface exists, but it is down! set it up.
    struct ifreq ifr;
    explicit_bzero(&ifr, sizeof(ifr));
    ifnamcpy(ifr.ifr_name, ifname);
    // get interface flags
    if (ioctl(socket_fd, SIOCGIFFLAGS, &ifr) < 0) {
        perror("SIOCGIFFLAGS");
        return -1;
    }
    // calculate new interface flags
    if (up == 0) {
        // set down
        ifr.ifr_flags &= ~IFF_UP;
    } else {
        // set up
        ifr.ifr_flags |= IFF_UP;
    }
    // set interface flags
    if (ioctl(socket_fd, SIOCSIFFLAGS, &ifr) < 0) {
        perror("SIOCSIFFLAGS");
        return -2;
    }
    return 0;
}

/**
 * checks whether the interface is up.
 *
 * returns 0 if it is down, 1 if it is up,
 * and -1 otherwise (e.g. if it's not up).
 *
 * you can call perror("SIOCGIFFLAGS") on -1.
 */
int test_if_up(const char *ifname) {
    struct ifreq ifr;
    explicit_bzero(&ifr, sizeof(ifr));
    ifnamcpy(ifr.ifr_name, ifname);
    // get interface flags
    if (ioctl(socket_fd, SIOCGIFFLAGS, &ifr) < 0) {
        // could not get flags, probably the interface doesn't exist
        return -1;
    }

    if (ifr.ifr_flags & IFF_UP) {
        return 1;
    } else {
        return 0;
    }
}

/**
 * returns the mac address of the given interface.
 *
 * returns 0 on success, -1 on failure.
 * calls perror on failure.
 */
int get_if_mac(const char *ifname, char *mac)
{
    struct ifreq ifr;
    explicit_bzero(&ifr, sizeof(ifr));
    ifnamcpy(ifr.ifr_name, ifname);
    if (ioctl(socket_fd, SIOCGIFHWADDR, &ifr) < 0) {
        perror("SIOCGIFHWADDR");
        return -1;
    }

    memcpy(mac, ifr.ifr_addr.sa_data, 6);
    return 0;
}

/**
 * finds the interface with the given mac (a 6-byte char array).
 * 
 * returns NULL if the interface was not found,
 * or the interface name otherwise.
 *
 * the lifetime of the returned interface name is until the next
 * invocation of this method.
 */
char *find_if_by_mac(const char *mac) {
    static char name[IF_NAMESIZE];

    struct ifaddrs *ifap = NULL;
    if (getifaddrs(&ifap) < 0) {
        perror("getifaddrs");
        return NULL;
    }

    for (struct ifaddrs *ifa = ifap; ifa; ifa = ifa->ifa_next) {
        if (ifa->ifa_addr && ifa->ifa_addr->sa_family == AF_PACKET) {
            struct sockaddr_ll *s = (struct sockaddr_ll*)ifa->ifa_addr;
            if (memcmp(s->sll_addr, mac, 6) == 0) {
                // found it
                ifnamcpy(name, ifa->ifa_name);
                freeifaddrs(ifap);
                return name;
            }
        }
    }

    freeifaddrs(ifap);
    return NULL;
}

/**
 * renames the interface.
 *
 * returns 0 on success, -1 on EBUSY, -2 on other errors.
 *
 * calls perror() on other errors.
 */
int rename_if(const char *old_name, const char *new_name) {
    struct ifreq ifr;
    explicit_bzero(&ifr, sizeof(ifr));
    ifnamcpy(ifr.ifr_name, old_name);
    ifnamcpy(ifr.ifr_newname, new_name);
    if (ioctl(socket_fd, SIOCSIFNAME, &ifr) < 0) {
        if (errno == EBUSY) {
            // probably because the interface is up
            return -1;
        } else {
            perror("SIOCSIFNAME");
            return -2;
        }
    }
    return 0;
}

/**
 * parses the mac address string to a 6-byte array.
 *
 * returns 0 on success, -1 on error.
 */
int parse_mac(const char *mac_string, char *mac) {
    if (strlen(mac_string) != 17) {
        return -1;
    }

    unsigned int values[6];
    int ret = sscanf(
        mac_string,
        "%02x:%02x:%02x:%02x:%02x:%02x%*c",
        &values[0], &values[1], &values[2], &values[3], &values[4], &values[5]
    );
    if (ret != 6) {
        return -1;
    }

    for (int i = 0; i < 6; i++) {
        if (values[i] > 255) {
            return -1;
        }
        mac[i] = values[i] & 0xff;
    }
    return 0;
}

void handle(const char *link_name, const char *mac) {
    int res = test_if_up(link_name);
    // TODO: as soon as IFF_UP is set in the interface flags,
    // we must perform some post-up action (e.g. add it to the wireguard cfg)
    if (res == 1) {
        // interface is up, all is fine.
        return;
    }

    if (res == 0) {
        // interface is down, set it up
        printf("interface '%s' is down; setting up\n", link_name);
        set_if_up(link_name, 1);
        return;
    }

    // the interface doesn't exist.
    // see if another interface exists which has the given mac,
    // and rename it.
    const char *old_link_name = find_if_by_mac(mac);
    if (old_link_name == NULL) {
        fprintf(stderr, "no interface with the required mac\n");
        return;
    }

    printf("interface %s: renaming to %s\n", old_link_name, link_name);
    switch (rename_if(old_link_name, link_name))
    {
    case 0:
        // success
        printf("interface successfully renamed\n");
        return;
    case -1:
        // EBUSY. set the interface down.
        printf("interface rename failed with EBUSY; setting down\n");
        set_if_up(old_link_name, 0);
        // try again in the next loop iteration
        return;
    default:
        // other error
        printf("failed to rename interface\n");
        return;
    }
}

int main(int argc, char **argv) {
    // parse arguments
    char mac[6];
    if (argc != 3 || parse_mac(argv[1], mac) < 0) {
        fprintf(stderr, "usage: %s mac linkname\n", argv[0]);
        return 1;
    }
    const char *link_name = argv[2];

    // open socket_fd
    socket_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (socket_fd < 0) {
        perror("socket");
        return 2;
    }

    while (1) {
        handle(link_name, mac);

        // yay, sleep-based polling!
        // the better solution would be to use udev, but this tool starts
        // running and must function during initrd, when udev isn't even
        // running yet.
        usleep(100000);
    }

    // cleanup
    close(socket_fd);
    return 0;
}
