"""Utils for parsing PBA augmentation schedules."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import ast
import collections
import tensorflow as tf

PbtUpdate = collections.namedtuple('PbtUpdate', [
    'target_trial_name', 'clone_trial_name', 'target_trial_epochs',
    'clone_trial_epochs', 'old_config', 'new_config'
])


def parse_log(file_path, epochs):
    """Parses augmentation policy schedule from log file.

  Args:
    file_path: Path to policy generated by running search.py.
    epochs: The number of epochs search was run for.

  Returns:
    A list containing the parsed policy of the form: [start epoch, start_epoch_clone, policy], where each element is a tuple of (num_epochs, policy list).
  """
    raw_policy = open(file_path, "r").readlines()
    raw_policy = [ast.literal_eval(line) for line in raw_policy]

    # Depreciated use case has policy as list instead of dict config.
    for r in raw_policy:
        for i in [4, 5]:
            if isinstance(r[i], list):
                r[i] = {"hp_policy": r[i]}
    raw_policy = [PbtUpdate(*r) for r in raw_policy]
    policy = []

    # Sometimes files have extra lines in the beginning.
    to_truncate = None
    for i in range(len(raw_policy) - 1):
        if raw_policy[i][0] != raw_policy[i + 1][1]:
            to_truncate = i
    if to_truncate is not None:
        raw_policy = raw_policy[to_truncate + 1:]

    # Initial policy for trial_to_clone_epochs.
    policy.append([raw_policy[0][3], raw_policy[0][4]["hp_policy"]])

    current = raw_policy[0][3]
    for i in range(len(raw_policy) - 1):
        # End at next line's trial epoch, start from this clone epoch.
        this_iter = raw_policy[i + 1][3] - raw_policy[i][3]
        assert this_iter >= 0, (i, raw_policy[i + 1][3], raw_policy[i][3])
        assert raw_policy[i][0] == raw_policy[i + 1][1], (i, raw_policy[i][0],
                                                          raw_policy[i + 1][1])
        policy.append([this_iter, raw_policy[i][5]["hp_policy"]])
        current += this_iter

    # Last cloned trial policy is run for (end - clone iter of last logged line)
    policy.append([epochs - raw_policy[-1][3], raw_policy[-1][5]["hp_policy"]])
    current += epochs - raw_policy[-1][3]
    assert epochs == sum([p[0] for p in policy])
    return policy


def parse_log_schedule(file_path, epochs, multiplier=1):
    """Parses policy schedule from log file.

  Args:
    file_path: Path to policy generated by running search.py.
    epochs: The number of epochs search was run for.
    multiplier: Multiplier on number of epochs for each policy in the schedule..

  Returns:
    List of length epochs, where index i contains the policy to use at epoch i.
  """
    policy = parse_log(file_path, epochs)
    schedule = []
    count = 0
    for num_iters, pol in policy:
        tf.logging.debug("iters {} by multiplier {} result: {}".format(
            num_iters, multiplier, num_iters * multiplier))
        for _ in range(int(num_iters * multiplier)):
            schedule.append(pol)
            count += 1
    if int(epochs * multiplier) - count > 0:
        tf.logging.info("len: {}, remaining: {}".format(
            count, epochs * multiplier))
    for _ in range(int(epochs * multiplier) - count):
        schedule.append(policy[-1][1])
    tf.logging.info("final len {}".format(len(schedule)))
    return schedule


if __name__ == "__main__":
    schedule = parse_log('schedules/rsvhn_16_wrn.txt', 160)
    for s in schedule:
        print(s)
