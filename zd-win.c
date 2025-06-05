/* zd-win */
/* Written for Windows + MinGW-W64 */
/* Author: Markus Thilo */
/* E-mail: markus.thilo@gmail.com */
/* License: GPL-3 */

/* Version */
const char *VERSION = "1.0.1_2025-06-05";

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <windows.h>
#include <winioctl.h>

/* Parameters to the target (file or device) */
typedef struct target_t {
	char *path;	// string with path to device or file
    HANDLE file;	// file descriptor
	LONGLONG size;	// the full size to work
	LONGLONG ptr; // pointer to position in file
	LONGLONG blocks;	// number of full blocks
	int leftbytes;	// number of bytes afte last full block
	int type;	// 0 = physical drive
} target_t;

/* Options for the wiping process */
typedef struct config_t {
	LONGLONG bs;	// size of blocks in bytes
	int bs64;	// size of blocks in 64 bit chunks (=bs/8)
	BYTE value;	// value to write and/or verify
	ULONGLONG value64;	// value expanded to 64 bits = 8 bytes
	BYTE *block;	// block to write
} config_t;

/* To handle bad blocks */
typedef struct badblocks_t {
	int cnt;	// counter for bad blocks
	int max;	// abort after
	int retry;	// limit retries
	LONGLONG *offsets;	// offsets
	char *errors;	// type of error
} badblocks_t;

/* Print help text */
void help(const int r) {
	printf("\n              000\n");
	printf("              000\n");
	printf("              000\n");
	printf("00000000  0000000\n");
	printf("   0000  0000 000\n");
	printf("  0000   000  000\n");
	printf(" 0000    0000 000\n");
	printf("00000000  0000000 for Windows\n\n");
	printf("v%s\n\n", VERSION);
	printf("Wipe drive or file\n\n");
	printf("Usage:\n");
	printf("zd-win.exe [OPTIONS] TARGET \n");
	printf("(or zd-win.exe -h for this help)\n\n");
	printf("TARGET:\n");
	printf("    Physical drive/file\n\n");
	printf("OPTIONS (optional):\n");
	printf("    -a : overwrite all bytes, do not check if already wiped\n");
	printf("    -b BLOCK_SIZE : block size for read and write (default is 4096)\n");
	printf("    -f VALUE : write this byte given in hex instead of 0\n");
	printf("    -m MAX_BAD_BLOCKS : abort after bad blocks (default is 200)\n");
	printf("    -r MAX_RETRIES : maximum retries after read or write error (default is 200)\n");
	printf("    -v : verify, do not wipe\n");
	printf("    -x : Two pass wipe (1st pass writes random bytes)\n\n");
	printf("Bad blocks will be listed as offset/[rwu]:\n");
	printf("    r: error occured while reading\n");
	printf("    w: error occured while writing\n");
	printf("    u: block is not wiped (unwiped)\n\n");
	printf("Example:\n");
	printf("zd-win.exe \\\\.\\PHYSICALDRIVE2\n\n");
	printf("Disclaimer:\n");
	printf("The author is not responsible for any loss of data.\n");
	printf("Obviously, this tool is dangerous as it is designed to erase data.\n\n");
	printf("Author: Markus Thilo\n");
	printf("License: GPL-3\n");
	printf("This CLI tool is part of the Wiper project:\n");
	printf("https://github.com/markusthilo/Wiper\n\n");
	exit(r);
}

/* Close target */
void close_target(const target_t *target) {
	if ( target->type == 0 && !DeviceIoControl(
		target->file,
		IOCTL_DISK_UPDATE_PROPERTIES,
		NULL,
		0,
		NULL,
		0,
		NULL,
		NULL
	) ) printf("\nWarning: could not update %s\n", target->path);
	if ( !CloseHandle(target->file) )
		fprintf(stderr, "\nWarning: could not close %s\n", target->path);
}

/* Set file pointer */
void set_pointer(target_t *target, const LONGLONG offset) {
	LARGE_INTEGER moveto;	// win still is not a real 64 bit system...
	moveto.QuadPart = target->ptr + offset;
	if ( !SetFilePointerEx(target->file, moveto, NULL, FILE_BEGIN) ) {
		fprintf(stderr, "Error: could not point to position %lld in %s\n",
			target->ptr + offset, target->path);
		close_target(target);
		exit(1);
	}
}

/* Set file pointer to 0 = beginning*/
void reset_pointer(target_t *target) {
	LARGE_INTEGER moveto;
	moveto.QuadPart = 0;
	if ( !SetFilePointerEx(target->file, moveto, NULL, FILE_BEGIN) ) {
		fprintf(stderr, "Error: could not point to the beginning of %s\n", target->path);
		close_target(target);
		exit(1);
	}
	target->ptr = 0;
}

/* Check if block is wiped */
int check_block(const ULONGLONG *block, const config_t *conf){
	for (int i=0; i<conf->bs64; i++) if ( block[i] != conf->value64 ) return -1;
	return 0;
}

/* Check if given quantity of bytes is wiped */
int check_bytes(const BYTE *block, const config_t *conf, const LONGLONG bs){
	for (int i=0; i<bs; i++) if ( block[i] != conf->value ) return -1;
	return 0;
}

/* Print bad blocks */
void print_bad_blocks(const badblocks_t *badblocks) {
	printf("Found %d bad block(s) (OFFSET/ERROR -> r = read error, w = write error, u = unwiped block):",
		badblocks->cnt);
	for (int i=0; i<badblocks->cnt; i++) {
			if ( i % 4 == 0 ) printf("\n");
			else printf("  ");
		printf("%*lld/%c", 20, badblocks->offsets[i], badblocks->errors[i]);
	}
	printf("\n");
}

/* Check for too many bad blocks */
void check_max_bad_blocks(const target_t *target, badblocks_t *badblocks) {
	if ( badblocks->max > badblocks->cnt++ ) return;
	close_target(target);
	printf("\n\n");
	print_bad_blocks(badblocks);
	fprintf(stderr, "Error: aborting because of too many bad blocks\n");
	exit(1);
}

/* Handle unwiped block */
void wipe_error(const target_t *target, badblocks_t *badblocks, const LONGLONG bs) {
	badblocks->offsets[badblocks->cnt] = target->ptr;
	badblocks->errors[badblocks->cnt] = 'u';
	check_max_bad_blocks(target, badblocks);
}

/* Handle read error */
int read_error(target_t *target, const config_t *conf, badblocks_t *badblocks, const LONGLONG bs) {
	BYTE *block = malloc(bs);
	DWORD ret;	// to check the returned number of bytes
	for (int pass=0; pass<badblocks->retry; pass++) {	// loop retries
		set_pointer(target, 0);
		if ( ReadFile(target->file, block, bs, &ret, NULL) && ret == bs ) return 0;
	}
	badblocks->offsets[badblocks->cnt] = target->ptr;	// add this bad block
	badblocks->errors[badblocks->cnt] = 'r';	// mark as read error
	check_max_bad_blocks(target, badblocks);
	set_pointer(target, bs);	// point to next block
	return -1;
}

/* Handle write error */
void write_error(target_t *target, const config_t *conf, badblocks_t *badblocks, const LONGLONG bs) {
	BYTE *block = malloc(bs);
	DWORD ret;	// to check the returned number of bytes
	for (int pass=0; pass<badblocks->retry; pass++) {	// loop retries
		set_pointer(target, 0);
		if ( WriteFile(target->file, conf->block, bs, &ret, NULL) && ret == bs ) return;
	}
	badblocks->offsets[badblocks->cnt] = target->ptr;	// add this bad block
	badblocks->errors[badblocks->cnt] = 'w';	// mark as read error
	check_max_bad_blocks(target, badblocks);
	set_pointer(target, bs);	// point to next block
}

/* Print progress */
clock_t print_progress(const target_t *target) {
	printf("\r...%*d%% / %*lld of%*lld bytes",
		4, (int)((100*target->ptr)/target->size), 20, target->ptr, 20, target->size);
	fflush(stdout);
	return time(NULL);
}

/* Wipe target, overwrite all */
void wipe_all(target_t *target, const config_t *conf, badblocks_t *badblocks) {
	DWORD ret;	// to check the returned number of bytes
	if ( target->size >= conf->bs ) {
		clock_t now = print_progress(target);
		for (off_t bc=0; bc<target->blocks; bc++) {
			if ( !WriteFile(target->file, conf->block, conf->bs, &ret, NULL) || ret != conf->bs )
				write_error(target, conf, badblocks, conf->bs);
			if ( time(NULL) > now ) now = print_progress(target);
			target->ptr += conf->bs;
		}
	}
	if ( target->leftbytes > 0 )
		if ( !WriteFile(target->file, conf->block, target->leftbytes, &ret, NULL) || ret != target->leftbytes )
			write_error(target, conf, badblocks, target->leftbytes);
	target->ptr = target->size;
	print_progress(target);
}

/* Convert value of a command line argument to integer >= 0, return -1 if NULL */
int uint_arg(const char *value, const char arg) {
	if ( value == NULL ) return -1;
	int res = atoi(value);
	if ( res >= 1 ) return res;
	if ( strcmp(value, "0") == 0 ) return 0;
	fprintf(stderr, "Error: -%c needs an unsigned integer value\n", arg);
	exit(1);
}

/* Print time delta */
void print_time(const time_t start_time) {
	int delta = time(NULL) - start_time;
	int hours = delta / 3600;
	delta -= hours * 3600;
	int minutes = delta / 60;
	delta -= minutes * 60;
	printf("\n\nProcess took ");
	if ( hours == 1 ) printf("1 hour, ");
	else if ( hours > 1 ) printf("%d hours, ", hours);
	if ( minutes == 1 ) printf("1 minute, ");
	else if ( minutes > 1 ) printf("%d minutes, ", minutes);
	if ( delta == 1 ) printf("1 second\n");
	else printf ("%d seconds\n", delta);
}

/* Main function - program starts here */
int main(int argc, char **argv) {
	if ( ( argc > 1 )	// show help
	&& ( ( ( argv[1][0] == '-' ) && ( argv[1][1] == '-' ) && ( argv[1][2] == 'h' ) )
	|| ( ( argv[1][0] == '-' ) && ( argv[1][1] == 'h' ) ) ) ) help(0);
	else if ( argc < 2 ) help(1);	// also show help if no argument is given but return with exit(1)
	char opt;	// command line options
	target_t target;	// drive or file
	config_t conf;	// options for wipe process
	badblocks_t badblocks;	// to abort after n bad blocks
	int todo = 0;	// 0 = selective wipe, 1 = all blocks, 2 = 2pass, 3 = verify
	time_t start_time;	// to measure
	char *barg = NULL, *farg = NULL, *marg = NULL, *rarg = NULL;	// pointer to command line args
	while ((opt = getopt(argc, argv, "avxb:f:m:r:")) != -1)	// command line arguments
		switch (opt) {
			case 'a': if ( todo == 0 ) { todo = 1; break; }
			case 'x': if ( todo == 0 ) { todo = 2; break; }
			case 'v': if ( todo == 0 ) { todo = 3; break; }
				fprintf(stderr, "Error: too many arguments\n");
				exit(1);
			case 'b': barg = optarg; break;	// get blocksize
	        case 'f': farg = optarg; break;	// get value to write and/or verify
			case 'm': marg = optarg; break;	// get value for max badb locks
			case 'r': rarg = optarg; break;	// get value for max retries
			case '?':
				switch (optopt) {
					case 'b': fprintf(stderr, "Error: option -b requires a value (blocksize)\n"); exit(1);
					case 'f': fprintf(stderr, "Error: option -f requires a value (integer)\n"); exit(1);
					default: help(1);
				}
			default: help(1);
		}
	if ( argc != optind+1 ) {	// check if there is one input file
		fprintf(stderr, "Error: one device or file to wipe is required\n");
		exit(1);
	}
	target.path = argv[optind];
	int bvalue = uint_arg(barg, 'b');
	if  ( bvalue == -1 ) conf.bs = 4096;	// default
	else if ( bvalue < 512 || bvalue > 32768 || bvalue % 512 != 0 ) {
		fprintf(stderr, "Error: block size has to be n * 512, >=512 and <=32768\n");
		exit(1);
	} else conf.bs = bvalue;
	conf.bs64 = conf.bs >> 3;	// number of 64 bit blocks = block size / 8
	conf.block = malloc(conf.bs);
	conf.value = 0;	//	default is to wipe with zeros
	conf.value64 = 0;
	if ( farg != NULL ) {
		unsigned long int fvalue = strtoul(farg, NULL, 16);
		if ( fvalue < 0 || fvalue > 0xff ) {	// check for 8 bits
			fprintf(stderr, "Error: value has to be inbetween 0 and 0xff\n");
			exit(1);
		}
		conf.value = (BYTE) fvalue;
		memset(&conf.value64, conf.value, sizeof(conf.value64));
	}
	badblocks.max = uint_arg(marg, 'm');
	if ( badblocks.max == -1 ) badblocks.max = 200;	// default
	badblocks.retry = uint_arg(rarg, 'r');
	if ( badblocks.retry == -1 ) badblocks.retry = 200;	// default
	if ( todo == 3 ) target.file = CreateFile(	// open device/file to read
		target.path,
		FILE_READ_DATA,
		FILE_SHARE_READ,
		NULL,
		OPEN_EXISTING,
		0,
		NULL
	); else target.file = CreateFile(	// to read and write
		target.path,
		FILE_READ_DATA | FILE_WRITE_DATA,
		FILE_SHARE_READ | FILE_SHARE_WRITE,
		NULL,
		OPEN_EXISTING,
		0,
		NULL
	);
	if ( target.file == INVALID_HANDLE_VALUE ) {
		fprintf(stderr, "Error: could not open %s\n", target.path);
		exit(1);
	}
	LARGE_INTEGER filesize;	// get size of file or drive
	if ( GetFileSizeEx(target.file, &filesize) ) {
		target.size = filesize.QuadPart;
		target.type = 1;
	} else {
		DISK_GEOMETRY_EX dge;	// disk?
		if ( DeviceIoControl(
			target.file,
			IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,
			NULL,
			0,
			&dge,
			sizeof(dge),
			NULL,
			NULL
		) )  {
			target.size = dge.DiskSize.QuadPart;
			target.type = 0;
		} else {
			fprintf(stderr, "Error: could not determin size of %s\n", target.path);
			exit(1);
		}
		if ( todo != 3 && !DeviceIoControl(
			target.file,
			IOCTL_DISK_DELETE_DRIVE_LAYOUT,
			NULL,
			0,
			NULL,
			0,
			NULL,
			NULL
		) ) {
			fprintf(stderr, "Error: could not delete drive layout of %s\n", target.path);
			exit(1);
		}
	}
	target.blocks = target.size / conf.bs;	// full blocks
	target.leftbytes = target.size % conf.bs;
	target.ptr = 0;
	badblocks.cnt = 0;
	badblocks.offsets = malloc(sizeof(ULONGLONG) * badblocks.max+1);
	badblocks.errors = malloc(sizeof(char) * badblocks.max+1);
	time(&start_time);
	switch (todo) {
		case 0:	// normal/selective wipe
			memset(conf.block, conf.value, conf.bs);
			printf("Wiping, pass 1 of 2\n");
			if ( target.size >= conf.bs ) {
				ULONGLONG *block = malloc(conf.bs);
				DWORD ret;	// to check the returned number of bytes
				clock_t now = print_progress(&target);
				for (LONGLONG bc=0; bc<target.blocks; bc++) {
					if ( !ReadFile(target.file, block, conf.bs, &ret, NULL)
						|| ret != conf.bs
						|| check_block(block, &conf) == -1
					) {	// overwrite block/page
						set_pointer(&target, 0);
						if ( !WriteFile(target.file, conf.block, conf.bs, &ret, NULL) || ret != conf.bs )
							write_error(&target, &conf, &badblocks, conf.bs);
					}
					if ( time(NULL) > now ) now = print_progress(&target);
					target.ptr += conf.bs;
				}
				if ( target.leftbytes > 0 ) {
					BYTE *block = malloc(target.leftbytes);
					DWORD ret;	// to get number of returned bytes
					if ( !ReadFile(target.file, block, target.leftbytes, &ret, NULL)
						|| ret != target.leftbytes
						|| check_bytes(block, &conf, target.leftbytes) == -1
					) {	// overwrite block/page
						set_pointer(&target, 0);
						if ( !WriteFile(target.file, conf.block, target.leftbytes, &ret, NULL)
							|| ret != target.leftbytes ) write_error(&target, &conf, &badblocks, target.leftbytes);
					}
				}
			}
			target.ptr = target.size;
			print_progress(&target);
			break;
		case 1:	// wipe all blocks
			memset(conf.block, conf.value, conf.bs);
			printf("Wiping, pass 1 of 2\n");
			wipe_all(&target, &conf, &badblocks);
			break;
		case 2:	// 2pass wipe
			for (int i=0; i<conf.bs; i++) conf.block[i] = (BYTE)rand();
			printf("Wiping, pass 1 of 3\n");
			wipe_all(&target, &conf, &badblocks);
			print_time(start_time);
			if ( badblocks.cnt > 0 ) {
				printf("Warning: finished 1st pass but found bad block(s)\n");
				print_bad_blocks(&badblocks);
			}
			badblocks.cnt = 0;
			reset_pointer(&target);
			time(&start_time);
			memset(conf.block, conf.value, conf.bs);
			printf("Wiping, pass 2 of 3\n");
			wipe_all(&target, &conf, &badblocks);
		case 3:	// verify
			memset(conf.block, conf.value, conf.bs);
	}
	if ( todo == 3 ) printf("Verifying\n");
	else {
		print_time(start_time);
		if ( badblocks.cnt > 0 ) {
			printf("Warning: finished wiping but found bad block(s)\n");
			print_bad_blocks(&badblocks);
		}
		reset_pointer(&target);
		time(&start_time);
		printf("Verifying, pass ");
		if ( todo == 2 ) printf("3 of 3\n");
		else printf("2 of 2\n");
	}
	badblocks.cnt = 0;	// verification pass
	if ( target.size >= conf.bs ) {
		DWORD ret;	// to check the returned number of bytes
		ULONGLONG *block = malloc(conf.bs);
		clock_t now = print_progress(&target);
		for (LONGLONG bc=0; bc<target.blocks; bc++) {
			if ( ( !ReadFile(target.file, block, conf.bs, &ret, NULL) || ret != conf.bs )
				&& read_error(&target, &conf, &badblocks, conf.bs) == -1 ) {
					target.ptr += conf.bs;
					continue;
				}
			if ( check_block(block, &conf) == -1 ) wipe_error(&target, &badblocks, conf.bs);
			if ( time(NULL) > now ) now = print_progress(&target);
			target.ptr += conf.bs;
		}
	}
	if ( target.leftbytes > 0 ) {
		DWORD ret;	// to check the returned number of bytes
		BYTE *block = malloc(target.leftbytes);
		if ( ( !ReadFile(target.file, block, target.leftbytes, &ret, NULL) || ret != target.leftbytes )
			&& read_error(&target, &conf, &badblocks, target.leftbytes) == 0
			&& check_bytes(block, &conf, target.leftbytes) == -1
		) wipe_error(&target, &badblocks, target.leftbytes);
		target.ptr = target.size;
	}
	print_progress(&target);
	print_time(start_time);
	close_target(&target);
	if ( badblocks.cnt > 0 ) {
		printf("Warning: all done but found %d bad block(s) in %s\n", badblocks.cnt, target.path);
		print_bad_blocks(&badblocks);
	} else printf("Verification was succesful, all done\n\n");
	exit(0);
}
