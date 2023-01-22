## Properties of CNN
Now lets see some properties of CNN which makes it unique and distinguised and exclusive.

### Sparse interaction
By making the kernel size small, CNN detects small meaningful features such as edges etc. This reduces memory requirements and computing the output requires fewer operation

In traditional neural network, for m input and n output we make m x n computation i.e. O(mxn). In CNN we limit each output node to have not more than k connections i.e. O(kxn) where k < m.

### Parameter sharing
In traditional neural network, each weight is tied to an input node, so the weight once multiplied is never visited again. In CNN each member of the kernel is used at every position of image.

### Equivariance to translation

To say that a function is equivariant means that if the input changes the output changes the same way.

While processing time series this means that convolution produces a sort of timeline that shows when differennt feature appear in the input. Image convolution creates a 2D map of where a feature appears in input. If we move the object in the input, its representation moves the same amount in the output.

Convolution aren't invariant to other translation such as change in the scale or rotation of the image.

## Advantages

### Shift invariance
CNN handles small shift in the input image i.e. even if the input image is shifted by a few pixels, the output remains the same. This is done using the pooling layer.

### Rotational/ Viewpoint invariance
This means that even if the image is rotated/inverted or the angle is changed, the output remains the same. This is not an intrinsic property of CNN rather this is handled using data augmentation i.e. transforming the input dataset to include all the cases.

### Size invariance
The network can handle varying size of input features. This is handled by Inception network. Inception network uses kernels of different sizes to handle varying size of input image.

### Spatial dependency
This is an intrinsic property of CNN. The pixel value is influenced by nearby pixel's value in image. CNN is designed in such a way to draw features from this type of data.

![Properties of CNN](/data/assets/deep_learning/properties_cnn.png)