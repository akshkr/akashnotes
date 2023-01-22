## Pooling layer

Now let's say you've a very large size image, something like 4000 x 3000. For a image this large, there will be too many input nodes and maybe large number nodes in hidden layer as well. So what do we do to reduce the image size? One option is to preprocess and reduce image dimension. Now let's look at a layer which resizes (reduces) image size without losing prominent features.

### Max pooling
In max pooling, we iterate over an image with a given window size and stride and pick the max value in the window as the output value.

![pooling](/data/assets/deep_learning/pooling.gif)

### Average pooling
In average pooling, we iterate similar to max pooling but pick the average value instead of maximum value.

Pooling helps to make the representation approx invariant to small translation of input. This means that even if the pixel value is slightly moved from the expected position, pooling handles that since we take maximum over a window size and the position of the pixel in the window doesn't matter.

### Advantages
- pooling reduces computational requirements by reducing the size of the image.
- It make the network translation invariant.

### Disadvantages
- It can complicate some kind of neural network architecture that uses top-down information such as Boltzmann machine and autoencoders.

### References
- [Pooling layer](https://arxiv.org/pdf/2009.07485.pdf)

