import nibabel as nib
import sys
import tempfile, os
sys.path.append('/home/grg/git/bbrc-validator/')
from bbrc.validation.utils import __is_valid_scan__
import numpy as np
import os.path as op
from matplotlib import pyplot as plt
from tqdm import tqdm
import pyxnat
# import urllib3

def download_resources(config_fp, experiment_id, resource_name, wd):
    x = pyxnat.Interface(config=config_fp)
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    t2_lut_names = ['T2_ALFA1']
    t2_scans = []
    e = x.select.experiment(experiment_id)
    scans = x.array.mrscans(experiment_id=experiment_id,\
            columns=['xnat:mrScanData/quality',
                     'xnat:mrScanData/type',
                     'xsiType']).data
    for s in scans:
        print(s)
        scan = e.scan(s['xnat:mrscandata/id'])

        if scan.attrs.get('type') in t2_lut_names and \
            __is_valid_scan__(x, s):
                t2_scans.append(scan.id())
    assert(len(t2_lut_names) == 1)

    filepaths = []
    t2_t1space = list(e.resource('ANTS').files('*%s*T1space.nii.gz'%t2_scans[0]))[0]
    fp1 = op.join(wd, '%s_T2_T1space.nii.gz'%experiment_id)
    filepaths.append(fp1)
    t2_t1space.get(fp1)

    r = e.resource(resource_name)
    for each in ['c1', 'c2', 'c3']:
        c = list(r.files('%s*.nii.gz'%each))[0]
        fp = op.join(wd, '%s_%s.nii.gz'%(experiment_id, each))
        c.get(fp)
        filepaths.append(fp)
    return filepaths


def snap_slices(slices, axis, row_size, figsize, func):
    def chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    paths = []
    bb = {}
    for a, chunk in enumerate(tqdm(chunks(slices, row_size))):
        _, path = tempfile.mkstemp(prefix='%s%s_'%(axis, a), suffix='.jpg')
        paths.append(path)
        bb[a] = []

        fig = plt.figure(dpi=300, figsize=figsize)

        for i, slice_index in enumerate(chunk):
            ax = fig.add_subplot(1, len(chunk), i+1, label='slice_%s'%slice_index)
            test = np.flip(np.swapaxes(np.abs(func(slice_index)), 0, 1), 0)
            xs, ys, zs = np.where(test!=0)
            bb[a].append((xs, ys, zs))
            test = test[min(xs):max(xs) + 1, min(ys):max(ys) + 1, :]

            ax.imshow(test, interpolation='none', )
            ax.axis('off')

        fig.savefig(path, facecolor=fig.get_facecolor(),
                bbox_inches='tight',
                transparent=True,
                pad_inches=0)
    return paths, bb


def snap_slices_orig(slices, axis, row_size, figsize, func, bb):
    def chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    paths = []

    for a, chunk in enumerate(tqdm(chunks(slices, row_size))):
        _, path = tempfile.mkstemp(prefix='%s%s_'%(axis, a), suffix='.jpg')
        paths.append(path)

        fig = plt.figure(dpi=300, figsize=figsize)

        for i, slice_index in enumerate(chunk):
            ax = fig.add_subplot(1, len(chunk), i+1, label='slice_%s'%slice_index)
            test = np.flip(np.swapaxes(np.abs(func(slice_index)), 0, 1), 0)
            xs, ys, zs = bb[a][i]
            test = test[min(xs):max(xs) + 1, min(ys):max(ys) + 1]

            ax.imshow(test, interpolation='none', cmap='gray')
            ax.axis('off')

        fig.savefig(path, facecolor=fig.get_facecolor(),
                bbox_inches='tight',
                transparent=True,
                pad_inches=0)
    return paths

def snap(filepaths, axes=['A', 'S', 'C'], orig=True):

    data = np.stack([np.asarray(nib.load(e).dataobj) for e in filepaths[1:]], axis=-1)
    orig_data = np.asarray(nib.load(filepaths[0]).dataobj)

    plt.rcParams['figure.facecolor'] = 'black'
    plt.rcParams.update({'figure.max_open_warning': 0})

    paths = {}
    paths_orig = {}

    if 'A' in axes:
        slices = range(100, data.shape[2] - 60, 3)
        path, bb = snap_slices(slices, axis='A', row_size=9, figsize=(37, 3),
            func=lambda x: data[:,:,x,:])
        paths['A'] = path

        if orig:
            path = snap_slices_orig(slices, axis='A', row_size=9, figsize=(37, 3),
                func=lambda x: orig_data[:,:,x], bb=bb)
            paths_orig['A'] = path

    if 'C' in axes:
        slices = range(50, data.shape[1] - 70, 3)
        path, bb = snap_slices(slices, axis='C', row_size=9, figsize=(40, 3),
            func=lambda x: data[:,x,:,:])
        paths['C'] = path

        if orig:
            path = snap_slices_orig(slices, axis='C', row_size=9, figsize=(40, 3),
                func=lambda x: orig_data[:,x,:], bb=bb)
            paths_orig['C'] = path

    if 'S' in axes:
        slices = range(90, data.shape[0] - 90, 1)
        path, bb = snap_slices(slices, axis='S', row_size=6, figsize=(18, 3),
            func=lambda x: data[x,:,:,:])
        paths['S'] = path

        if orig:
            path = snap_slices_orig(slices, axis='S', row_size=6, figsize=(18, 3),
                func=lambda x: orig_data[x,:,:], bb=bb)
            paths_orig['S'] = path

    return paths, paths_orig


def run(config_fp, experiment_id, resource_name, axes, orig, opacity, fp):
    wd = '/tmp/'
    # Downloading resources
    print('Downloading resources...')
    filepaths = download_resources(config_fp, experiment_id, resource_name, wd)

    # Creating snapshots (along given axes and original if needed)
    print('Creating snapshots...')
    paths, paths_orig = snap(filepaths, axes=axes, orig=orig)

    montage_cmd = 'montage -resize 1000x -tile 1 -background black -geometry +0+0 %s %s'
    # Compiling images into a single one (one per axis)
    for each in axes:
        cmd = montage_cmd%(' '.join(paths[each]), fp.replace('.jpg', '_%s.jpg'%each))
        print(cmd)
        os.system(cmd)
        for e in paths[each]:
            os.unlink(e) # Delete individual snapshots

    # Create one image with the selected axes
    cmd = montage_cmd%(' '.join([fp.replace('.jpg', '_%s.jpg'%each) for each in axes]), fp)
    print(cmd)
    os.system(cmd)

    if orig:
        # Repeat the process (montage) with the "raw" snapshots
        for each in axes:
            cmd = montage_cmd%(' '.join(paths_orig[each]), fp.replace('.jpg', '_orig_%s.jpg'%each))
            print(cmd)
            os.system(cmd)
            for e in paths_orig[each]:
                os.unlink(e)

        # Create one image with the selected axes
        cmd = montage_cmd%(' '.join([fp.replace('.jpg', '_orig_%s.jpg'%each) for each in axes]),
                fp.replace('.jpg', '_orig.jpg'))
        print(cmd)
        os.system(cmd)

    # At this point there should be two images max. (segmentation and raw image)
    composite_cmd = 'composite -dissolve %s -gravity Center %s %s -alpha Set %s'

    if orig:
        if opacity == -1: # will generate a .gif

            # Fading from raw data to segmentation
            for i in range(0, 100, 10):
                cmd = composite_cmd %(i, fp, fp.replace('.jpg', '_orig.jpg'),
                        fp.replace('.jpg', '_fusion_%03d.jpg'%i))
                print(cmd)
                os.system(cmd)

            # From segmentation to raw data
            for i in range(0, 100, 10):
                cmd = composite_cmd %(100-i, fp, fp.replace('.jpg', '_orig.jpg'),
                        fp.replace('.jpg', '_fusion_%03d.jpg'%(100+i)))
                print(cmd)
                os.system(cmd)

            # Collect frames and create gif
            filepaths = []
            for i in range(0, 200, 10):
                filepaths.append(fp.replace('.jpg', '_fusion_%03d.jpg'%i))

            cmd = 'convert -delay 20 -loop 0 %s %s'\
                %(' '.join(filepaths), fp.replace('.jpg', '.gif'))
            print(cmd)
            os.system(cmd)

        else:

            # Blends the two images (segmentation and original) into a composite one
            cmd = composite_cmd %(opacity, fp, fp.replace('.jpg', '_orig.jpg'),
                    fp.replace('.jpg', '_fusion.jpg'))
            print(cmd)
            os.system(cmd)
            print('Saved in %s'%fp.replace('.jpg', '_fusion.jpg'))


if __name__ == '__main__':
    experiment_id = 'BBRCDEV_E02849'
    fp = '/tmp/fusion.jpg'
    resource_name = 'SPM12_SEGMENT_T2T1_COREG'
    config_fp = '/home/grg/.xnat_goperto_ci.cfg'
    axes = 'S'
    opacity = 100
    orig = True
    run(config_fp, experiment_id, resource_name, axes, orig, opacity, fp)
