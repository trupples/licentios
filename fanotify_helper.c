#include <stdio.h>
#include <unistd.h>
#include <stdbool.h>
#include <string.h>
#include <sys/fanotify.h>
#include <fcntl.h>

int main(int argc, char **argv)
{
    int ret;
    char buf[1024];

    // Parse args
    if(argc != 2)
    {
        printf("Usage:\n"
        "\t%s <mountpoint>\n", argv[0]);
        return 1;
    }

    const char *mountpoint = argv[1];

    int fd = fanotify_init(FAN_CLASS_NOTIF | FAN_UNLIMITED_QUEUE, O_RDONLY);
    if(fd == -1)
    {
        perror("fanotify_init");
        return 1;
    }

    ret = fanotify_mark(fd, FAN_MARK_ADD | FAN_MARK_MOUNT, FAN_ACCESS, AT_FDCWD, argv[1]);
    if(ret == -1)
    {
        perror("fanotify_mark");
        return 1;
    }

    while(true)
    {
        int num = read(fd, &buf, sizeof(buf));
        if(num == -1)
        {
            break;
        }

        struct fanotify_event_metadata *meta = (struct fanotify_event_metadata *) buf;
        while(FAN_EVENT_OK(meta, num))
        {
            char linkname[20], pathname[1024];
            snprintf(linkname, sizeof(linkname), "/proc/self/fd/%d", meta->fd);
            int pathlen = readlink(linkname, pathname, sizeof(pathname));
            pathname[pathlen] = '\0';
            close(meta->fd);

            puts(pathname);

            meta = FAN_EVENT_NEXT(meta, num);
        }
    }

    return 0;
}
