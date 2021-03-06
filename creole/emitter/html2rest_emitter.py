#!/usr/bin/env python
# coding: utf-8

"""
    html -> reStructuredText Emitter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Links about reStructuredText:

    http://openalea.gforge.inria.fr/doc/openalea/doc/_build/html/source/sphinx/rest_syntax.html

    :copyleft: 2011-2012 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

from __future__ import division, absolute_import, print_function, unicode_literals
import posixpath

from creole.shared.base_emitter import BaseEmitter
from creole.shared.markup_table import MarkupTable


# Kink of nodes in which hyperlinks are stored in references intead of embedded urls.
DO_SUBSTITUTION = ("th", "td",) # TODO: In witch kind of node must we also substitude links?


class Html2restException(Exception):
    pass


class ReStructuredTextEmitter(BaseEmitter):
    """
    Build from a document_tree (html2creole.parser.HtmlParser instance) a
    creole markup text.
    """
    def __init__(self, *args, **kwargs):
        super(ReStructuredTextEmitter, self).__init__(*args, **kwargs)

        self.table_head_prefix = "_. "
        self.table_auto_width = False

        self._substitution_data = []
        self._used_substitution_links = {}
        self._used_substitution_images = {}
        self._list_markup = ""

    def _get_block_data(self):
        """
        return substitution bock data
        e.g.:
        .. _link text: /link/url/
        .. |substitution| image:: /image.png
        """
        content = "\n".join(self._substitution_data)
        self._substitution_data = []
        return content

    #--------------------------------------------------------------------------

    def blockdata_pre_emit(self, node):
        """ pre block -> with newline at the end """
        pre_block = self.deentity.replace_all(node.content).strip()
        pre_block = "\n".join(["    %s" % line for line in pre_block.splitlines()])
        return "::\n\n%s\n\n" % pre_block

    def inlinedata_pre_emit(self, node):
        """ a pre inline block -> no newline at the end """
        return "<pre>%s</pre>" % self.deentity.replace_all(node.content)

    def blockdata_pass_emit(self, node):
        return "%s\n\n" % node.content
        return node.content

    #--------------------------------------------------------------------------

    def emit_children(self, node):
        """Emit all the children of a node."""
        return "".join(self.emit_children_list(node))

    def emit(self):
        """Emit the document represented by self.root DOM tree."""
        return self.emit_node(self.root).rstrip()

    def document_emit(self, node):
        self.last = node
        result = self.emit_children(node)
        if self._substitution_data:
            # add rest at the end
            result += "%s\n\n" % self._get_block_data()

        result = result.replace('\n ', '\n')
        result = result.replace('**+--', '**\n\n+--')
        if result.endswith('----'):
            result = result[:-4]
        return result

    def emit_node(self, node):
        result = ""
        if self._substitution_data and node.parent == self.root:
            result += "%s\n\n" % self._get_block_data()

        result += super(ReStructuredTextEmitter, self).emit_node(node)
        return result

    def p_emit(self, node):
        res = "\n%s\n\n" % self.emit_children(node).strip()
        return res

    HEADLINE_DATA = {
        1:("=", True),
        2:("-", True),
        3:("=", False),
        4:("-", False),
        5:('`', False),
        6:("'", False),
    }
    def headline_emit(self, node):
        text = self.emit_children(node)

        level = node.level
        if level > 6:
            level = 6

        char, both = self.HEADLINE_DATA[level]
        markup = char * len(text)

        if both:
            format = "%(m)s\n%(t)s\n%(m)s\n\n"
        else:
            format = "%(t)s\n%(m)s\n\n"

        return format % {"m":markup, "t":text}

    #--------------------------------------------------------------------------

    def _typeface(self, node, key):
        data = self.emit_children(node)
        stripped = data.strip()

        if len(stripped) > 50:
            return data

        if len(stripped) > 2 and stripped[0] == '|' and stripped[-1] == '|':
            return data

        if (len(stripped) > 3 and stripped[0] == '`' and stripped[-2] == '`'
            and stripped[-1] == '_'):
            return data

        if len(stripped) > 2 and stripped[0] == '*' and stripped[-1] == '*':
            return data

        if (stripped != '' and '\n' not in stripped and '\t' not in stripped
            and '*' not in stripped):

            return key + stripped + key + ' '
        else:
            return data

    def strong_emit(self, node):
        return self._typeface(node, key="**")
    def b_emit(self, node):
        return self._typeface(node, key="**")
    big_emit = strong_emit

    def i_emit(self, node):
        return self._typeface(node, key="*")
    def em_emit(self, node):
        return self._typeface(node, key="*")

    def tt_emit(self, node):
        return self._typeface(node, key="``")

    def small_emit(self, node):
        # FIXME: Is there no small in ReSt???
        return self.emit_children(node)

#    def sup_emit(self, node):
#        return self._typeface(node, key="^")
#    def sub_emit(self, node):
#        return self._typeface(node, key="~")
#    def del_emit(self, node):
#        return self._typeface(node, key="-")
#
#    def cite_emit(self, node):
#        return self._typeface(node, key="??")
#    def ins_emit(self, node):
#        return self._typeface(node, key="+")
#
#    def span_emit(self, node):
#        return self._typeface(node, key="%")
#    def code_emit(self, node):
#        return self._typeface(node, key="@")

    #--------------------------------------------------------------------------

    def hr_emit(self, node):
        return "----\n\n"

    def _should_do_substitution(self, node):
        node = node.parent

        if node.kind in DO_SUBSTITUTION:
            return True

        if node is not self.root:
            return self._should_do_substitution(node)
        else:
            return False

    def _get_old_substitution(self, substitution_dict, text, url):
        if text not in substitution_dict:
            # save for the next time
            substitution_dict[text] = url
        else:
            # text has links with the same link text
            old_url = substitution_dict[text]
            if old_url == url:
                # same url -> substitution can be reused
                return old_url
            else:
                msg = (
                    "Duplicate explicit target name:"
                    " substitution was used more than one time, but with different URL."
                    " - link text: %r url1: %r url2: %r"
                ) % (text, old_url, url)
                raise Html2restException(msg)

    def a_emit(self, node):
        link_text = self.emit_children(node)
        link_text = link_text.strip()

        if link_text == '':
            return ''

        if 'href' not in node.attrs:
            return ''

        if link_text.startswith('**') and link_text.endswith('**'):
            link_text = link_text[2:-1]

        url = node.attrs["href"]
        if url.startswith('http://assets.acr-dijon'):
            return self.img_emit(node.children[0])

        num = 1
        sub = link_text
        while True:
            try:
                old_url = self._get_old_substitution(self._used_substitution_links, sub, url)

                break
            except Html2restException:
                sub = link_text + ' #%d' % num
                num += 1
        link_text = sub

        if self._should_do_substitution(node):
            # make a hyperlink reference
            if not old_url:
                # new substitution
                self._substitution_data.append(
                    ".. _%s: %s" % (link_text, url)
                )
            return "`%s`_ " % link_text

        if old_url:
            # reuse a existing substitution
            return "`%s`_ " % link_text
        else:
            # create a inline hyperlink
            return "`%s <%s>`_ " % (link_text, url)

    def img_emit(self, node):
        if 'src' not in node.attrs:
            return ''
        src = node.attrs["src"]

        if src.split(':')[0] == 'data':
            return ""

        title = node.attrs.get("title", "")
        alt = node.attrs.get("alt", "")
        if len(alt) > len(title): # Use the longest one
            substitution_text = alt
        else:
            substitution_text = title

        if substitution_text == "": # Use filename as picture text
            substitution_text = posixpath.basename(src)

        num = 0
        sub = substitution_text
        while True:
            try:
                old_src = self._get_old_substitution(
                    self._used_substitution_images, sub, src
                    )

                break
            except Html2restException:
                sub = substitution_text + ' #%d' % num
                num += 1
        substitution_text = sub

        if not old_src:
            self._substitution_data.append(
                ".. |%s| image:: %s" % (substitution_text, src)
            )

        return " |%s| " % substitution_text

    #--------------------------------------------------------------------------

    def code_emit(self, node):
        return "``%s``" % self._emit_content(node)

    #--------------------------------------------------------------------------

    def li_emit(self, node):
        content = self.emit_children(node).strip("\n")
        result = "\n%s%s %s\n" % (
            "    " * (node.level - 1), self._list_markup, content
        )
        return result

    def _list_emit(self, node, list_type):
        self._list_markup = list_type
        content = self.emit_children(node)

        if node.level == 1:
            # FIXME: This should be made ​​easier and better
            complete_list = "\n\n".join([i.strip("\n") for i in content.split("\n") if i])
            content = "%s\n\n" % complete_list

        return content

    def ul_emit(self, node):
        return self._list_emit(node, "*")

    def ol_emit(self, node):
        return self._list_emit(node, "#.")

    def table_emit(self, node):
        """
        http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html#tables
        """
        self._table = MarkupTable(
            head_prefix="",
            auto_width=True,
            debug_msg=self.debug_msg
        )
        self.emit_children(node)
        content = self._table.get_rest_table()
        return "\n\n%s\n\n" % content


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())

#    import sys;sys.exit()
    from creole.parser.html_parser import HtmlParser

    data = """<p>A nested bullet lists:</p>
<ul>
<li><p>item 1</p>
<ul>
<li><p>A <strong>bold subitem 1.1</strong> here.</p>
<ul>
<li>subsubitem 1.1.1</li>
<li>subsubitem 1.1.2 with inline <img alt="substitution text" src="/url/to/image.png" /> image.</li>
</ul>
</li>
<li><p>subitem 1.2</p>
</li>
</ul>
</li>
<li><p>item 2</p>
<ul>
<li>subitem 2.1</li>
</ul>
</li>
</ul>
<p>Text under list.</p>
<p>4 <img alt="PNG pictures" src="/image.png" /> four</p>
<p>5 <img alt="Image without files ext?" src="/path1/path2/image" /> five</p>
"""

    print(data)
    h2c = HtmlParser(
#        debug=True
    )
    document_tree = h2c.feed(data)
    h2c.debug()

    e = ReStructuredTextEmitter(document_tree,
        debug=True
    )
    content = e.emit()
    print("*" * 79)
    print(content)
    print("*" * 79)
    print(content.replace(" ", ".").replace("\n", "\\n\n"))

