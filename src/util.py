import pyxel as px

dict_numkey = {
    px.KEY_1: 1,
    px.KEY_2: 2,
    px.KEY_3: 3,
    px.KEY_4: 4,
    px.KEY_5: 5,
    px.KEY_6: 6,
    px.KEY_7: 7,
    px.KEY_8: 8,
    px.KEY_9: 9,
    px.KEY_0: 0,
}


def loop(target, dist, length, min_val=0):
    if dist is None:
        return target
    value = target + dist if target else dist
    if value >= length + min_val:
        value -= length
    if value < min_val:
        value += length
    return value


def range(target, dist, max_val, min_val=0):
    if dist is None:
        return target
    value = target + dist if target else dist
    return min(max(value, min_val), max_val)


def numkey():
    for key, value in dict_numkey.items():
        if px.btnp(key):
            return key, value
    return None, None


def rlkey():
    if px.btnp(px.KEY_RIGHT, 10, 2):
        return 1
    if px.btnp(px.KEY_LEFT, 10, 2):
        return -1
    return None


def udkey():
    if px.btnp(px.KEY_UP, 10, 2):
        return -1
    if px.btnp(px.KEY_DOWN, 10, 2):
        return 1
    return None
