from nml import grfstrings
from nml.actions import base_action, action7


class Action14(base_action.BaseAction):
    def __init__(self, nodes):
        self.nodes = nodes

    def skip_action7(self):
        return False

    def write(self, file):
        size = 2 # final 0-byte
        for node in self.nodes: size += node.get_size()

        file.start_sprite(size)
        file.print_bytex(0x14)
        for node in self.nodes:
            node.write(file)
        file.print_bytex(0)

        file.end_sprite()


class Action14Node(object):
    def __init__(self, type_string, id):
        self.type_string = type_string
        self.id = id

    def get_size(self):
        """
        How many bytes will be written to the output file by L{write}?

        @return: The size (in bytes) of this node.
        """
        raise NotImplementedError('get_size must be implemented in Action14Node-subclass %r' % type(self))

    def write(self, file):
        """
        Write this node to the output file.

        @param file: The file to write the output to.
        """
        raise NotImplementedError('write must be implemented in Action14Node-subclass %r' % type(self))

    def write_type_id(self, file):
        file.print_string(self.type_string, False, True)
        if isinstance(self.id, basestring):
            file.print_string(self.id, False, True)
        else:
            file.print_dword(self.id)

class TextNode(Action14Node):
    def __init__(self, id, string, skip_default_langid = False):
        Action14Node.__init__(self, "T", id)
        self.string = string
        self.skip_default_langid = skip_default_langid

    def get_size(self):
        size = 0
        for translation in grfstrings.grf_strings[self.string.name.value]:
            if self.skip_default_langid and translation['lang'] == 0x7F: continue
            # 6 is for "T" (1), id (4), langid (1)
            size += 6 + grfstrings.get_string_size(translation['text'])
        return size

    def write(self, file):
        for translation in grfstrings.grf_strings[self.string.name.value]:
            if self.skip_default_langid and translation['lang'] == 0x7F: continue
            self.write_type_id(file)
            file.print_bytex(translation['lang'])
            file.print_string(translation['text'])
            file.newline()

class BranchNode(Action14Node):
    def __init__(self, id):
        Action14Node.__init__(self, "C", id)
        self.subnodes = []

    def get_size(self):
        size = 6 # "C", id, final 0-byte
        for node in self.subnodes:
            size += node.get_size()
        return size

    def write(self, file):
        self.write_type_id(file)
        file.newline()
        for node in self.subnodes:
            node.write(file)
        file.print_bytex(0)
        file.newline()

class BinaryNode(Action14Node):
    def __init__(self, id, size, val = None):
        Action14Node.__init__(self, "B", id)
        self.size = size
        self.val = val

    def get_size(self):
        return 7 + self.size # "B" (1), id (4), size (2), data (self.size)

    def write(self, file):
        self.write_type_id(file)
        file.print_word(self.size)
        file.print_varx(self.val, self.size)
        file.newline()

class SettingMaskNode(BinaryNode):
    def __init__(self, param_num, first_bit, num_bits):
        BinaryNode.__init__(self, "MASK", 3)
        self.param_num = param_num
        self.first_bit = first_bit
        self.num_bits = num_bits

    def write(self, file):
        self.write_type_id(file)
        file.print_word(self.size)
        file.print_byte(self.param_num)
        file.print_byte(self.first_bit)
        file.print_byte(self.num_bits)
        file.newline()

class LimitNode(BinaryNode):
    def __init__(self, min_val, max_val):
        BinaryNode.__init__(self, "LIMI", 8)
        self.min_val = min_val
        self.max_val = max_val

    def write(self, file):
        self.write_type_id(file)
        file.print_word(self.size)
        file.print_dword(self.min_val)
        file.print_dword(self.max_val)
        file.newline()

def grf_name_desc_actions(name, desc):
    root = BranchNode("INFO")
    if len(grfstrings.grf_strings[name.name.value]) > 1:
        name_node = TextNode("NAME", name, True)
        root.subnodes.append(name_node)
    if len(grfstrings.grf_strings[desc.name.value]) > 1:
        desc_node = TextNode("DESC", desc, True)
        root.subnodes.append(desc_node)
    if len(root.subnodes) > 0:
        return [Action14([root])]
    return []

def param_desc_actions(params):
    num_params = 0
    for param_desc in params:
        num_params += len(param_desc.setting_list)
    root = BranchNode("INFO")
    root.subnodes.append(BinaryNode("NPAR", 1, num_params))
    param_root = BranchNode("PARA")
    param_num = 0
    setting_num = 0
    for param_desc in params:
        if param_desc.num is not None:
            param_num = param_desc.num.value
        for setting in param_desc.setting_list:
            setting_node = BranchNode(setting_num)
            if setting.name_string is not None:
                setting_node.subnodes.append(TextNode("NAME", setting.name_string))
            if setting.desc_string is not None:
                setting_node.subnodes.append(TextNode("DESC", setting.desc_string))
            if setting.type == 'int':
                setting_node.subnodes.append(BinaryNode("MASK", 1, param_num))
                min_val = setting.min_val.value if setting.min_val is not None else 0
                max_val = setting.max_val.value if setting.max_val is not None else 0xFFFFFFFF
                setting_node.subnodes.append(LimitNode(min_val, max_val))
            else:
                assert setting.type == 'bool'
                setting_node.subnodes.append(BinaryNode("TYPE", 1, 1))
                bit = setting.bit_num.value if setting.bit_num is not None else 0
                setting_node.subnodes.append(SettingMaskNode(param_num, bit, 1))
            if setting.def_val is not None:
                setting_node.subnodes.append(BinaryNode("DFLT", 4, setting.def_val.value))
            param_root.subnodes.append(setting_node)
            setting_num += 1
        param_num += 1
    if len(param_root.subnodes) > 0:
        root.subnodes.append(param_root)
    return [Action14([root])]
