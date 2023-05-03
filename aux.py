def is_lens(node):
    return any(d.func.id == 'lens' for d in node.decorator_list)

def get_at(node):
    return [d for d in node.decorator_list
            if d.func.id == 'at'][0].args[0].value
