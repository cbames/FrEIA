import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class PermuteRandom(nn.Module):
    '''permutes input vector in a random but fixed way'''

    def __init__(self, dims_in, seed):
        super().__init__()

        self.in_channels = dims_in[0][0]

        np.random.seed(seed)
        self.perm = np.random.permutation(self.in_channels)
        np.random.seed()

        self.perm_inv = np.zeros_like(self.perm)
        for i, p in enumerate(self.perm):
            self.perm_inv[p] = i

        self.perm = torch.LongTensor(self.perm)
        self.perm_inv = torch.LongTensor(self.perm_inv)

    def forward(self, x, rev=False):
        if not rev:
            return [x[0][:, self.perm]]
        else:
            return [x[0][:, self.perm_inv]]

    def jacobian(self, x, rev=False):
        # TODO: use batch size, set as nn.Parameter so cuda() works
        return 0.

    def output_dims(self, input_dims):
        assert len(input_dims) == 1, "Can only use 1 input"
        return input_dims


class FixedLinearTransform(nn.Module):
    '''Fixed transformation according to y = Mx + b, with invertible
    matrix M.'''

    def __init__(self, dims_in, M, b):
        super().__init__()

        self.M = nn.Parameter(M.t(), requires_grad=False)
        self.M_inv = nn.Parameter(M.t().inverse(), requires_grad=False)
        self.b = nn.Parameter(b, requires_grad=False)

        self.logDetM = nn.Parameter(torch.log(torch.cholesky(M).diag()).sum(),
                                    requires_grad=False)

    def forward(self, x, rev=False):

        if not rev:
            return [x[0].mm(self.M) + self.b]
        else:
            return [(x[0]-self.b).mm(self.M_inv)]

    def jacobian(self, x, rev=False):
        if rev:
            return -self.logDetM.expand(x[0].shape[0])
        else:
            return self.logDetM.expand(x[0].shape[0])

    def output_dims(self, input_dims):
        return input_dims

class LogitTransform(nn.Module): 
    ''' The logit is the inverse of the sigmoid. Thus the inverse of this layer
    when scaled properly will be bounded, this helps to avoid boundary problems '''

    def __init__(self, dims_in, scaling = 0.99):
        super().__init__()

        self.scaling = scaling
        self.last_jac = 0 
        self.mine = mine 

    def forward(self, x, rev=False):

        def safe_log(x):
            return torch.log(x.clamp(min=1e-22))

        if not rev:
            # Scale to contract inside [0, 1]
            z = ((2 * x[0] - 1) * self.scaling + 1) / 2
            # Apply logit to map to unbounded space
            transformed_x = safe_log(z) - safe_log(1 - z)

            # log Jacobian of the scaled state, we can ignore the scale because it's constant.
            self.last_jac = (-safe_log(z) - safe_log(1. - z) ).sum(-1) 
            return [transformed_x]

        else:
            # Reverse the logit
            z = torch.sigmoid(x[0])
            # log Jacobian of the x[0]
            self.last_jac =  (safe_log(z) + safe_log(1. - z) ).sum(-1)
            return [z]

    def jacobian(self, x, rev=False):
        return self.last_jac

    def output_dims(self, input_dims):
        return input_dims
# class LogitTransform(nn.Module): 
#     ''' The logit is the inverse of the sigmoid. Thus the inverse of this layer
#     when scaled properly will be bounded, this helps to avoid boundary problems '''

#     def __init__(self, dims_in):
#         super().__init__()

#         self.last_jac = 0 

#     def forward(self, x, rev=False):

#         def safe_log(x):
#             return torch.log(x.clamp(min=1e-13))


#         if not rev:

#             # Apply logit to map to unbounded space
#             transformed_x = safe_log(x[0]) - safe_log(1 - x[0])
#             # log Jacobian of the transformed state 
#             self.last_jac = (-safe_log(x[0]) - safe_log(1 - x[0])).sum(-1) 
#             return [transformed_x]

#         else:

#             # Reverse the logit
#             z = torch.sigmoid(x[0])
#             # log jac of the sigmoid 
#             self.last_jac = (safe_log(z) + safe_log(1. - z) ).sum(-1) 
#             return [z]

#     def jacobian(self, x, rev=False):
#         return self.last_jac

#     def output_dims(self, input_dims):
#         return input_dims


class Fixed1x1Conv(nn.Module):
    '''Fixed 1x1 conv transformation with matrix M.'''

    def __init__(self, dims_in, M):
        super().__init__()

        self.M = nn.Parameter(M.t().view(*M.shape, 1, 1), requires_grad=False)
        self.M_inv = nn.Parameter(M.t().inverse().view(*M.shape, 1, 1), requires_grad=False)

        self.logDetM = nn.Parameter(torch.log(torch.det(M).abs()).sum(),
                                    requires_grad=False)

    def forward(self, x, rev=False):
        if not rev:
            return [F.conv2d(x[0], self.M)]
        else:
            return [F.conv2d(x[0], self.M_inv)]

    def jacobian(self, x, rev=False):
        if rev:
            return -self.logDetM.expand(x[0].shape[0])
        else:
            return self.logDetM.expand(x[0].shape[0])

    def output_dims(self, input_dims):
        return input_dims

import warnings

def _deprecated_by(orig_class):
    class deprecated_class(orig_class):
        def __init__(self, *args, **kwargs):

            warnings.warn(F"{self.__class__.__name__} is deprecated and will be removed in the public release. "
                          F"Use {orig_class.__name__} instead.",
                          DeprecationWarning)
            super().__init__(*args, **kwargs)

    return deprecated_class

permute_layer = _deprecated_by(PermuteRandom)
linear_transform = _deprecated_by(FixedLinearTransform)
conv_1x1 = _deprecated_by(Fixed1x1Conv)
