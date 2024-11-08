// This is C code hamfisted to C++ just for an easy to use std::set<std::string>
#include <set>
#include <string>

#include <stdio.h>
#include <stdlib.h>
#include <sys/mount.h>
#include <unistd.h>
#include <signal.h>
#include <sys/fanotify.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>


char g_temp_dir[] = "mountXXXXXX";
bool g_running = true;

void sigint_handler(int)
{
    fprintf(stderr, "Caught SIGINT, stopping\n");

    // Access one last dummy file so the read() call exits
    std::string dummy = std::string(g_temp_dir) + "/.dummy";
    FILE *f = fopen(dummy.c_str(), "w+");
    fputc('!', f);
    fgetc(f);
    fclose(f);

    g_running = false;
}

int main(int argc, char **argv)
{
    int ret; // C -like error handling in C++, what a joy!
    const size_t BUFSIZE = 1024;
    char *buf = new char[BUFSIZE];
    std::set<std::string> paths;

    /* Fanotify lags behind (at least on WSL) and may still have files to give
     * us even minutes after the build process ended. Thus, stopping at Ctrl-C
     * will miss files from the last part of the build process. To counteract
     * this, Ctrl-C will trigger a create+read of a `.dummy` file, which marks
     * the actual end. Between SIGINT and finally reading the `.dummy` file, 
     * the state will be `g_running == false && got_dummy == false`. */
    bool got_dummy = false;

    // "Parse" args
    if(argc != 3)
    {
        printf("Usage:\n"
        "\t%s <folder_to_watch> <pathfile>\n", argv[0]);
        return 1;
    }

    FILE *pathfile = strcmp(argv[2], "-") ? fopen(argv[2], "w") : stdin;
    if(pathfile == NULL)
    {
        perror("fopen");
        ret = 1;
        goto done;
    }

    // Prepare filesystem - create temp directory
    if(mkdtemp(g_temp_dir) == NULL)
    {
        perror("mkdtemp");
        ret = 1;
        goto done_close_pathfile;
    }

    // Prepare filesystem - bind-mount watched directory to temp dir
    if(mount(argv[1], g_temp_dir, NULL, MS_BIND, NULL) == -1)
    {
        perror("mount");
        ret = 1;
        goto done_rmdir;
    }

    if(signal(SIGINT, sigint_handler) == SIG_ERR)
    {
        perror("signal");
        ret = 1;
        goto done_umount;
    }

    int fanfd;
    if((fanfd = fanotify_init(FAN_CLASS_NOTIF | FAN_UNLIMITED_QUEUE, O_RDONLY)) == -1)
    {
        perror("fanotify_init");
        ret = 1;
        goto done_umount;
    }

    if(fanotify_mark(fanfd, FAN_MARK_ADD | FAN_MARK_MOUNT, FAN_ACCESS, AT_FDCWD, g_temp_dir) == -1)
    {
        perror("fanotify_mark");
        ret = 1;
        goto done_fanotify;
    }

    fprintf(stderr, "Watching accessed files within `%s` (bound to `%s`).\n"
                    "Run your code, then Ctrl-C to stop watching.\n\n",
                    g_temp_dir, argv[1]);

    while(g_running || !got_dummy)
    {
        int num = read(fanfd, buf, BUFSIZE);
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

            if(strstr(pathname, "/.dummy"))
            {
                fprintf(stderr, "Got .dummy -- end of list!\n");
                got_dummy = true;
            }

            // Process pathname
            // Is it new?
            if(paths.insert(pathname).second)
            {
                puts(pathname);
                fprintf(pathfile, "%s\n", pathname);
            }

            meta = FAN_EVENT_NEXT(meta, num);
        }
    }

    printf("Saved %ld accessed paths to `%s`\n", paths.size(), argv[2]);

    ret = 0;

done_fanotify:
    close(fanfd);
done_umount:
    umount(g_temp_dir);
done_rmdir:
    rmdir(g_temp_dir);
done_close_pathfile:
    fclose(pathfile);
done:
    return ret;
}
