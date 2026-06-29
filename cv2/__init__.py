import numpy as np
from PIL import Image, ImageFilter, ImageOps
COLOR_BGR2GRAY=0; COLOR_RGB2BGR=1; COLOR_RGB2GRAY=2; IMREAD_GRAYSCALE=0; CV_64F=0; ADAPTIVE_THRESH_GAUSSIAN_C=0; THRESH_BINARY=0

def imwrite(path, img):
    arr=np.asarray(img)
    if arr.ndim==3: arr=arr[...,::-1]
    Image.fromarray(arr.astype('uint8')).save(path); return True

def imread(path, flags=None):
    im=Image.open(path)
    if flags==IMREAD_GRAYSCALE: return np.array(im.convert('L'))
    return np.array(im.convert('RGB'))[...,::-1]

def cvtColor(img, code):
    arr=np.asarray(img)
    if code in (COLOR_BGR2GRAY, COLOR_RGB2GRAY):
        if arr.ndim==2: return arr
        return (0.299*arr[...,2] + 0.587*arr[...,1] + 0.114*arr[...,0]).astype('uint8') if code==COLOR_BGR2GRAY else (0.299*arr[...,0] + 0.587*arr[...,1] + 0.114*arr[...,2]).astype('uint8')
    if code==COLOR_RGB2BGR: return arr[...,::-1]
    return arr

def Laplacian(gray, dtype):
    g=np.asarray(gray,dtype=float)
    out=np.zeros_like(g)
    out[1:-1,1:-1]=g[:-2,1:-1]+g[2:,1:-1]+g[1:-1,:-2]+g[1:-1,2:]-4*g[1:-1,1:-1]
    return out

def fastNlMeansDenoising(gray): return np.asarray(gray).astype('uint8')
def adaptiveThreshold(img, maxValue, adaptiveMethod, thresholdType, blockSize, C):
    arr=np.asarray(img); return np.where(arr > arr.mean()-C, maxValue, 0).astype('uint8')
def filter2D(src, ddepth, kernel): return np.asarray(src).astype('uint8')
def equalizeHist(gray): return np.array(ImageOps.equalize(Image.fromarray(np.asarray(gray).astype('uint8'))))
class _CLAHE:
    def apply(self,img): return equalizeHist(img)
def createCLAHE(clipLimit=2.0,tileGridSize=(8,8)): return _CLAHE()
