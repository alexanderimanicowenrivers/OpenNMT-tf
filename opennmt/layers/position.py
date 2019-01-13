"""Define position encoder classes."""

import math
import abc
import six

import numpy as np
import tensorflow as tf

from opennmt.layers.reducer import SumReducer


@six.add_metaclass(abc.ABCMeta)
class PositionEncoder(tf.keras.layers.Layer):
  """Base class for position encoders."""

  def __init__(self, reducer=SumReducer(), name=None):
    super(PositionEncoder, self).__init__(name=name)
    self.reducer = reducer

  def call(self, inputs, position=None):
    """Apply position encoding to inputs.

    Args:
      inputs: The inputs of shape :math:`[B, T, D]`.
      position: If known, the position to encode (1-indexed).

    Returns:
      A ``tf.Tensor`` of shape :math:`[B, T, D]` where :math:`D` depends on the
      :attr:`reducer`.
    """
    batch_size = tf.shape(inputs)[0]
    timesteps = tf.shape(inputs)[1]
    input_dim = inputs.get_shape().as_list()[-1]

    if position is None:
      positions = tf.range(timesteps) + 1
    else:
      positions = [position]
    position_encoding = self.encode([positions], input_dim)
    position_encoding = tf.tile(position_encoding, [batch_size, 1, 1])
    return self.reducer([inputs, position_encoding])

  @abc.abstractmethod
  def encode(self, positions, depth):
    """Creates position encodings.

    Args:
      position: The positions to encode of shape :math:`[B, ...]`.
      depth: The encoding depth :math:`D`.

    Returns:
      A ``tf.Tensor`` of shape :math:`[B, ..., D]`.
    """
    raise NotImplementedError()


class PositionEmbedder(PositionEncoder):
  """Encodes position with a lookup table."""

  def __init__(self, maximum_position=128, reducer=SumReducer()):
    """Initializes the position encoder.

    Args:
      maximum_position: The maximum position to embed. Positions greater
        than this value will be set to :obj:`maximum_position`.
      reducer: A :class:`opennmt.layers.reducer.Reducer` to merge inputs and
        position encodings.
    """
    super(PositionEmbedder, self).__init__(
        reducer=reducer, name="position_encoding")
    self.maximum_position = maximum_position
    self.embeddings = None

  def build(self, input_shape):
    """Creates the embedding variable."""
    input_depth = input_shape.as_list()[-1]
    embeddings_shape = [self.maximum_position + 1, input_depth]
    self.embeddings = self.add_weight("w_embs", embeddings_shape)
    super(PositionEmbedder, self).build(input_shape)

  def encode(self, positions, depth):
    positions = tf.minimum(positions, self.maximum_position)
    return tf.nn.embedding_lookup(self.embeddings, positions)


class SinusoidalPositionEncoder(PositionEncoder):
  """Encodes positions with sine waves as described in
  https://arxiv.org/abs/1706.03762.
  """

  def encode(self, positions, depth):
    if depth % 2 != 0:
      raise ValueError("SinusoidalPositionEncoder expects the depth to be divisble "
                       "by 2 but got %d" % depth)

    batch_size = tf.shape(positions)[0]
    positions = tf.cast(positions, tf.float32)

    log_timescale_increment = math.log(10000) / (depth / 2 - 1)
    inv_timescales = np.exp(np.arange(depth / 2, dtype=np.float32) * -log_timescale_increment)
    inv_timescales = tf.reshape(tf.tile(inv_timescales, [batch_size]), [batch_size, -1])
    scaled_time = tf.expand_dims(positions, -1) * tf.expand_dims(inv_timescales, 1)
    encoding = tf.concat([tf.sin(scaled_time), tf.cos(scaled_time)], axis=2)
    return tf.cast(encoding, self.dtype)
