# Convolution Neural network

Convolution neural networks or CNN is a revolutionary algorithm used in modeling image data. Images are nothing but numbers, very similar to any other tabular data, but with a few fundamental differences. One, Image pixels are associated with nearby pixels. If I provide you with a long list of image pixel values, it might mean nothing, but when you know the nearby pixels of an area, it forms some meaningful property of the image, so it's very important to understand the relation of pixels nearby each other. Second, there are a lot of pixels in an image, so if we link one input node (pixel) with one edge to the next layer, we might end up having a very large number of trainable parameters. So CNN used something called parameter sharing to optimise that.

## Convolution layer

Convolution neural networks are designed to extract features from images to differentiate one image from another. The preprocessing required in this type of network is very less compared to other algorithms that work on images.

The major advantage of CNN or convolution layer is Spatial dependency. Spatial Dependency means a pixel's value is influenced by nearby pixel's value in image. This is because generally they all belong to same color because they are from same object. There are more advantages of CNN but let's dive into the algorithm first.

### Algorithm

You might know that image is nothing but a collection of pixels i.e. a collection on numbers. Typically an image has 3 layers (Red, Green, Blue) but here to introduce convolution we've taken single layered image or GrayScale image.

Let's say we have a small image as follow

```python
[[0.1, 0.2, 0.3],
[0.4, 0.5, 0.6],
[0.7, 0.8, 0.9]]
```

and a kernel as:

```python
[[1, 0, 1],
[0, 1, 0],
[1, 0, 1]]
```

Now for one convolution operation we take sum of products pixel wise i.e.
```
0.1x1 + 0.2x0 + 0.3x1 + 0.4x0 + 0.5x1 + 0.6x0 + 0.7x1 + 0.8x0 + 0.9x1 = 2.5
```

Now to summarize this is how convolution operation is done.

![conv operation](/data/assets/deep_learning/conv_oper.png)

Here is another example of how convolution layer is performed on a image to get a feature map.

![animated conv](/data/assets/deep_learning/anim_conv_oper.gif)

Let's observe the dimension of image and feature map (output after applying covolution layer). For an image of 5x5 and filter 3x3 we got a feature map of 3x3. Can we devise a formula for output image size given input image dimension and kernel size?

$$ output\_dimension = input\_dimension - kernel\_dimension + 1 $$

so for our example i.e. input_dimension = 5 and kernel_dimension = 3 we have output size 5-3+1 = 3.

### Padding
Now you can see the border and the corner of the image had lesser operation than other part of image. Also the dimension is constantly reducing, which limits the number of times we can apply convolution operation. To avoid this we use padding, a very simple concept - add 0 values to the borner of image.


image before padding:

```python
[[0.1, 0.2, 0.3],
[0.4, 0.5, 0.6],
[0.7, 0.8, 0.9]]
```

image after same padding of one pixel:

```python
[[0, 0,  0,   0,   0],
[0, 0.1, 0.2, 0.3, 0],
[0, 0.4, 0.5, 0.6, 0],
[0, 0.7, 0.8, 0.9, 0],
[0, 0,   0,   0,   0]]
```

### Stride
We saw in the above convolution operation that the kernel moves one pixel to the right and bottom while convolution operation. What if we increase the pixel gap between two convolution operation. Following image will it more clear.

![strides](/data/assets/deep_learning/strides.gif)

This is convolution operation on a padded image (dotted lines are paddding) with strides as 2. Now can you guess why we need to increase the stride? Yes, you are right - to decrease the image size. This is generally followed when the input image size is quite large.

Now you see we need a new formula to calculate output image size:

$$ output\_dimension = \frac{input\_dimension - kernel\_dimension + 2 \times padding}{strides} + 1

