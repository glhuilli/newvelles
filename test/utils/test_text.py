import unittest

from numpy import array

from newvelles.utils.text import process_content
from newvelles.utils.text import remove_subsets, remove_similar_subsets

TEST_CASES = {
    'Limbic is a package.': ['limbic', 'package'],
    'a random number 111': ['random', 'number'],
    "something I didn't expected to test with l'huillier.":
    ['didnt', 'expected', 'test', 'lhuillier'],
    "l'huillier is a last name a will not change.": ["l'huillier", "change"],
    "didn't will be removed (stopword).": ["removed", 'stopword'],
    '': ['']
}
TERMS_MAPPING = {'dog': 'cat'}
TEST_CASES_TERMS_MAPPING = {'this is a dog': 'this is a cat'}
TEST_SET_CASES = [
    ([[0, 1, 3], [0, 1], [2], [0, 3], [4], [0, 3, 2]], {(0, 1, 2, 3), (4, )}), ([[0]], [[0]]),
    ([], set()), ([[0, 1], [0, 1]], {(0, 1)}),
    ([[0, 1], [1, 2], [2, 4], [3, 4], [9, 8, 7, 6, 5, 4]], {(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)}),
    (
        [(237, ), (63, ), (356, ), (127, ), (246, ), (365, ), (115, 87), (310, ), (374, ), (319, ),
         (20, ), (84, ), (257, 167), (29, ), (148, ), (93, ), (38, ), (276, ), (102, ), (221, ),
         (47, ), (166, ), (285, ), (111, ), (230, ), (349, ), (175, ), (239, ), (358, ), (184, ),
         (303, ), (320, 160, 134, 145, 50, 51, 116, 114, 157), (367, ), (193, 139), (312, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 314, 58, 316, 315, 317, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207,
          211, 212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (13, ), (77, ), (86, ),
         (31, ), (150, ), (95, ), (214, ), (40, ), (320, 160, 134, 145, 114, 50, 116, 51, 157),
         (49, ), (342, ), (168, ), (113, ), (232, ), (351, ), (177, ), (296, ), (305, ), (369, ),
         (15, ), (79, ), (24, ), (143, ), (88, ), (33, ), (152, ), (271, ), (97, ), (42, ), (335, ),
         (280, ), (106, ), (344, ), (170, ), (289, ), (234, ), (353, ), (179, ), (243, ), (362, ),
         (371, ), (241, 318), (8, ), (17, ), (81, ), (200, ), (264, ), (90, ), (209, ), (35, ),
         (328, ), (154, ), (99, ), (218, ), (44, ), (337, ), (282, ), (108, ), (163, ), (227, ),
         (172, ), (236, ), (355, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 58, 315, 314, 317, 316, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211, 212,
          213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (300, ), (65, ), (10, ), (74, ),
         (19, ), (83, ), (291, 287), (147, ), (92, ), (37, ), (156, ), (330, ), (101, ), (339, ),
         (165, ), (1, 4, 9, 41, 22), (293, ),
         (321, 129, 341, 151, 222, 223, 224, 225, 100, 36, 104, 233), (357, ),
         (321, 129, 341, 151, 222, 223, 224, 225, 36, 100, 104, 233),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 314, 315, 316, 317, 58, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211, 212,
          213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (3, ),
         (160, 320, 134, 145, 50, 51, 116, 114, 157), (67, ), (186, ), (12, ), (131, ), (352, 290),
         (21, ), (140, ), (85, ), (204, ), (30, ), (149, ), (354, 61, 62), (94, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 58, 314, 316, 315, 317, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187,
          190, 202, 206, 207, 211, 212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255),
         (332, ), (158, ), (277, ), (350, ), (295, ), (359, ), (60, ), (153, 331, 110), (5, ),
         (124, ), (69, ), (188, ), (14, ), (133, ), (174, 112, 210, 216), (78, ), (197, ), (23, ),
         (32, 0, 2, 322, 43, 11, 48), (261, ), (380, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 58, 315, 316, 317, 314, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211,
          212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (325, ), (334, ), (27, 28),
         (343, ), (288, ), (346, 373), (53, ), (192, 194, 195, 198, 199, 182, 376, 191), (117, ),
         (220, 215), (181, ), (7, ), (126, ), (320, 160, 134, 145, 50, 114, 51, 116, 157), (71, ),
         (16, ), (309, ), (254, ), (80, ), (135, ), (25, ), (144, ),
         (320, 160, 134, 145, 50, 114, 116, 51, 157), (89, ), (208, ), (327, ), (336, ), (345, ),
         (61, 62, 354), (52, 378, 141), (55, ), (120, 122, 348, 159),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 314, 315, 316, 58, 317, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211, 212,
          213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (119, ), (238, ), (64, ), (183, ),
         (302, ), (128, ), (366, ), (73, ), (18, ), (137, ), (311, ), (375, ), (201, ), (82, ),
         (265, ), (259, 250, 253), (274, ), (250, 259, 253), (338, ),
         (320, 134, 145, 157, 160, 50, 51, 116, 114), (39, ), (103, ), (287, 291),
         (0, 32, 2, 322, 11, 43, 48), (231, ), (347, ), (176, ), (121, ), (66, ), (185, ), (304, ),
         (130, ), (249, ), (75, ), (368, ), (313, ), (258, ), (377, ), (203, ), (340, ), (96, ),
         (105, ), (169, ), (139, 193), (59, ), (123, ), (242, ), (361, ), (132, ), (251, ), (370, ),
         (196, ), (107, 109), (378, 52, 141), (379, ), (205, ), (324, ), (333, ), (34, ), (162, ),
         (226, ), (235, ),
         (6, 56, 57, 58, 68, 72, 76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202,
          206, 207, 211, 212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255, 256, 260, 263,
          266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292, 294, 297, 298, 299,
          301, 306, 307, 308, 314, 315, 316, 317, 323, 329), (180, ), (125, ), (70, ), (363, ),
         (189, ), (110, 153, 331), (372, ), (26, 46), (262, ), (326, ), (360, 364), (91, ), (155, ),
         (45, ), (283, ), (228, ), (54, ), (173, )],
        [(237, ), (63, ), (356, ), (127, ), (246, ), (365, ), (115, 87), (310, ), (374, ), (319, ),
         (20, ), (84, ), (257, 167), (29, ), (148, ), (93, ), (38, ), (276, ), (102, ), (221, ),
         (47, ), (166, ), (285, ), (111, ), (230, ), (349, ), (175, ), (239, ), (358, ), (184, ),
         (303, ), (320, 160, 134, 145, 50, 51, 116, 114, 157), (367, ), (193, 139), (312, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 314, 58, 316, 315, 317, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207,
          211, 212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (13, ), (77, ), (86, ),
         (31, ), (150, ), (95, ), (214, ), (40, ), (320, 160, 134, 145, 114, 50, 116, 51, 157),
         (49, ), (342, ), (168, ), (113, ), (232, ), (351, ), (177, ), (296, ), (305, ), (369, ),
         (15, ), (79, ), (24, ), (143, ), (88, ), (33, ), (152, ), (271, ), (97, ), (42, ), (335, ),
         (280, ), (106, ), (344, ), (170, ), (289, ), (234, ), (353, ), (179, ), (243, ), (362, ),
         (371, ), (241, 318), (8, ), (17, ), (81, ), (200, ), (264, ), (90, ), (209, ), (35, ),
         (328, ), (154, ), (99, ), (218, ), (44, ), (337, ), (282, ), (108, ), (163, ), (227, ),
         (172, ), (236, ), (355, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 58, 315, 314, 317, 316, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211, 212,
          213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (300, ), (65, ), (10, ), (74, ),
         (19, ), (83, ), (291, 287), (147, ), (92, ), (37, ), (156, ), (330, ), (101, ), (339, ),
         (165, ), (1, 4, 9, 41, 22), (293, ),
         (321, 129, 341, 151, 222, 223, 224, 225, 100, 36, 104, 233), (357, ),
         (321, 129, 341, 151, 222, 223, 224, 225, 36, 100, 104, 233),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 314, 315, 316, 317, 58, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211, 212,
          213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (3, ),
         (160, 320, 134, 145, 50, 51, 116, 114, 157), (67, ), (186, ), (12, ), (131, ), (352, 290),
         (21, ), (140, ), (85, ), (204, ), (30, ), (149, ), (354, 61, 62), (94, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 58, 314, 316, 315, 317, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187,
          190, 202, 206, 207, 211, 212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255),
         (332, ), (158, ), (277, ), (350, ), (295, ), (359, ), (60, ), (153, 331, 110), (5, ),
         (124, ), (69, ), (188, ), (14, ), (133, ), (174, 112, 210, 216), (78, ), (197, ), (23, ),
         (32, 0, 2, 322, 43, 11, 48), (261, ), (380, ),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 58, 315, 316, 317, 314, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211,
          212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (325, ), (334, ), (27, 28),
         (343, ), (288, ), (346, 373), (53, ), (192, 194, 195, 198, 199, 182, 376, 191), (117, ),
         (220, 215), (181, ), (7, ), (126, ), (320, 160, 134, 145, 50, 114, 51, 116, 157), (71, ),
         (16, ), (309, ), (254, ), (80, ), (135, ), (25, ), (144, ),
         (320, 160, 134, 145, 50, 114, 116, 51, 157), (89, ), (208, ), (327, ), (336, ), (345, ),
         (61, 62, 354), (52, 378, 141), (55, ), (120, 122, 348, 159),
         (256, 260, 6, 263, 266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292,
          294, 297, 298, 299, 301, 306, 307, 308, 56, 57, 314, 315, 316, 58, 317, 323, 68, 72, 329,
          76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202, 206, 207, 211, 212,
          213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255), (119, ), (238, ), (64, ), (183, ),
         (302, ), (128, ), (366, ), (73, ), (18, ), (137, ), (311, ), (375, ), (201, ), (82, ),
         (265, ), (259, 250, 253), (274, ), (250, 259, 253), (338, ),
         (320, 134, 145, 157, 160, 50, 51, 116, 114), (39, ), (103, ), (287, 291),
         (0, 32, 2, 322, 11, 43, 48), (231, ), (347, ), (176, ), (121, ), (66, ), (185, ), (304, ),
         (130, ), (249, ), (75, ), (368, ), (313, ), (258, ), (377, ), (203, ), (340, ), (96, ),
         (105, ), (169, ), (139, 193), (59, ), (123, ), (242, ), (361, ), (132, ), (251, ), (370, ),
         (196, ), (107, 109), (378, 52, 141), (379, ), (205, ), (324, ), (333, ), (34, ), (162, ),
         (226, ), (235, ),
         (6, 56, 57, 58, 68, 72, 76, 98, 118, 136, 138, 142, 146, 161, 164, 171, 178, 187, 190, 202,
          206, 207, 211, 212, 213, 217, 219, 229, 240, 244, 245, 247, 248, 252, 255, 256, 260, 263,
          266, 267, 268, 269, 270, 272, 273, 275, 278, 279, 281, 284, 286, 292, 294, 297, 298, 299,
          301, 306, 307, 308, 314, 315, 316, 317, 323, 329), (180, ), (125, ), (70, ), (363, ),
         (189, ), (110, 153, 331), (372, ), (26, 46), (262, ), (326, ), (360, 364), (91, ), (155, ),
         (45, ), (283, ), (228, ), (54, ), (173, )],
    ),
    ([
        array([0, 25]),
        array([1]),
        array([2, 22]),
        array([3, 25]),
        array([4, 17, 22, 38]),
        array([5]),
        array([6]),
        array([7, 11, 25, 41, 47, 319]),
        array([8]),
        array([9]),
        array([
            10, 34, 73, 99, 120, 146, 168, 172, 207, 214, 215, 219, 221, 250, 258, 262, 274, 280,
            299, 307, 308, 309, 327
        ]),
        array([7, 11, 41, 47, 319]),
        array([12]),
        array([13, 16]),
        array([14]),
        array([15]),
        array([13, 16, 22]),
        array([4, 17]),
        array([18]),
        array([19, 20]),
        array([19, 20, 46]),
        array([21]),
        array([2, 4, 16, 22, 37, 44]),
        array([23, 47]),
        array([24, 31]),
        array([0, 3, 7, 25, 47, 319]),
        array([26]),
        array([27]),
        array([28]),
        array([29]),
        array([30]),
        array([24, 31]),
        array([32, 319]),
        array([33]),
        array([10, 34]),
        array([35]),
        array([36]),
        array([22, 37]),
        array([4, 38]),
        array([39]),
        array([40]),
        array([7, 11, 41, 47, 319]),
        array([42]),
        array([43]),
        array([22, 44, 47]),
        array([45]),
        array([20, 46]),
        array([7, 11, 23, 25, 41, 44, 47, 319]),
        array([48]),
        array([49]),
        array([50, 241]),
        array([51, 183, 193, 196, 199, 200]),
        array([52]),
        array([53]),
        array([54, 113, 175, 212, 218]),
        array([55, 118, 137, 149, 342]),
        array([56, 149, 162]),
        array([57]),
        array([58]),
        array([59, 271]),
        array([60, 270, 271]),
        array([61]),
        array([62]),
        array([63]),
        array([64]),
        array([65]),
        array([66]),
        array([67, 72, 168, 172, 274, 299, 327]),
        array([68]),
        array([69]),
        array([70]),
        array([71]),
        array([67, 72, 99, 168, 213, 215, 274, 276, 280, 295, 299]),
        array([10, 73, 207, 215, 258, 265, 309]),
        array([74]),
        array([75]),
        array([76]),
        array([77]),
        array([78]),
        array([79]),
        array([80]),
        array([81]),
        array([82]),
        array([83]),
        array([84]),
        array([85]),
        array([86]),
        array([87]),
        array([88, 379]),
        array([89]),
        array([90]),
        array([91]),
        array([92]),
        array([93]),
        array([94]),
        array([95]),
        array([96]),
        array([97]),
        array([98]),
        array([10, 72, 99, 120, 168, 214, 215, 219, 221, 280, 299, 307, 327]),
        array([100]),
        array([101]),
        array([102]),
        array([103]),
        array([104]),
        array([105]),
        array([106]),
        array([107]),
        array([108]),
        array([109, 111]),
        array([110]),
        array([109, 111]),
        array([112, 210]),
        array([54, 113, 175, 212, 218]),
        array([114, 321]),
        array([115]),
        array([116, 157, 163]),
        array([117]),
        array([55, 118, 161, 342]),
        array([119]),
        array([
            10, 99, 120, 146, 168, 172, 191, 213, 214, 215, 219, 221, 250, 258, 262, 280, 299, 309,
            327
        ]),
        array([121]),
        array([122]),
        array([123]),
        array([124]),
        array([125]),
        array([126]),
        array([127]),
        array([128]),
        array([129]),
        array([130]),
        array([131, 314]),
        array([132]),
        array([133]),
        array([134]),
        array([135, 321, 325, 344]),
        array([136]),
        array([55, 137, 342]),
        array([138]),
        array([139, 149, 342]),
        array([140]),
        array([141]),
        array([142]),
        array([143, 194]),
        array([144]),
        array([145, 341]),
        array([10, 120, 146, 219, 250, 258, 280, 299, 307, 309]),
        array([147, 165]),
        array([148, 341, 344, 373]),
        array([55, 56, 139, 149, 342]),
        array([150, 298, 300]),
        array([151]),
        array([152]),
        array([153]),
        array([154]),
        array([155, 316]),
        array([156]),
        array([116, 157, 163]),
        array([158]),
        array([159]),
        array([160]),
        array([118, 161]),
        array([56, 162, 343]),
        array([116, 157, 163, 381]),
        array([164, 298]),
        array([147, 165, 324]),
        array([166]),
        array([167]),
        array([
            10, 67, 72, 99, 120, 168, 172, 191, 213, 214, 215, 219, 221, 231, 250, 258, 274, 280,
            299, 307, 308, 309, 327
        ]),
        array([169]),
        array([170]),
        array([171]),
        array([10, 67, 120, 168, 172, 215, 221, 262, 299, 327]),
        array([173]),
        array([174]),
        array([54, 113, 175, 212, 218]),
        array([176]),
        array([177]),
        array([178]),
        array([179]),
        array([180]),
        array([181]),
        array([182]),
        array([51, 183, 193, 195, 196, 200, 371]),
        array([184]),
        array([185]),
        array([186]),
        array([187]),
        array([188, 191]),
        array([189]),
        array([190]),
        array([120, 168, 188, 191, 213]),
        array([192, 193, 196]),
        array([51, 183, 192, 193, 195, 196, 199, 200]),
        array([143, 194]),
        array([183, 193, 195, 196, 199, 200]),
        array([51, 183, 192, 193, 195, 196, 199, 200]),
        array([197]),
        array([198]),
        array([51, 193, 195, 196, 199, 200]),
        array([51, 183, 193, 195, 196, 199, 200, 371]),
        array([201]),
        array([202]),
        array([203, 213, 231, 247, 276, 280]),
        array([204]),
        array([205]),
        array([206]),
        array([10, 73, 207, 208, 213, 219, 250, 258, 309]),
        array([207, 208]),
        array([209]),
        array([112, 210]),
        array([211]),
        array([54, 113, 175, 212, 218]),
        array([72, 120, 168, 191, 203, 207, 213, 219, 250, 274, 299]),
        array([10, 99, 120, 168, 214, 215, 219, 221, 231, 280, 299, 307, 327]),
        array(
            [10, 72, 73, 99, 120, 168, 172, 214, 215, 219, 221, 274, 276, 280, 299, 307, 309, 327]),
        array([216, 314]),
        array([217, 222]),
        array([54, 113, 175, 212, 218]),
        array([10, 99, 120, 146, 168, 207, 213, 214, 215, 219, 221, 250, 258, 274, 299, 327]),
        array([220]),
        array([10, 99, 120, 168, 172, 214, 215, 219, 221, 231, 274, 276, 280, 299, 308]),
        array([217, 222]),
        array([223]),
        array([224]),
        array([225, 226]),
        array([225, 226, 316]),
        array([227]),
        array([228]),
        array([229]),
        array([230]),
        array([168, 203, 214, 221, 231, 280, 307, 309, 327]),
        array([232]),
        array([233]),
        array([234]),
        array([235, 314]),
        array([236]),
        array([237]),
        array([238]),
        array([239]),
        array([240]),
        array([50, 241]),
        array([242]),
        array([243]),
        array([244]),
        array([245]),
        array([246, 268]),
        array([203, 247, 262]),
        array([248]),
        array([249, 258]),
        array([10, 120, 146, 168, 207, 213, 219, 250, 258, 262, 280, 299, 309]),
        array([251]),
        array([252, 255]),
        array([253]),
        array([254, 269]),
        array([252, 255, 261]),
        array([256]),
        array([257, 268]),
        array([10, 73, 120, 146, 168, 207, 219, 249, 250, 258, 265, 280, 299, 308, 309]),
        array([259]),
        array([260]),
        array([255, 261]),
        array([10, 120, 172, 247, 250, 262, 276, 280, 299, 309]),
        array([263]),
        array([264]),
        array([73, 258, 265, 309]),
        array([266]),
        array([267]),
        array([246, 257, 268]),
        array([254, 269, 273]),
        array([60, 270, 271]),
        array([59, 60, 270, 271, 274, 282, 295, 378]),
        array([272]),
        array([269, 273]),
        array([10, 67, 72, 168, 213, 215, 219, 221, 271, 274, 276, 280, 295, 299, 307]),
        array([275]),
        array([72, 203, 215, 221, 262, 274, 276, 280, 299]),
        array([277]),
        array([278]),
        array([279, 282]),
        array([
            10, 72, 99, 120, 146, 168, 203, 214, 215, 221, 231, 250, 258, 262, 274, 276, 280, 285,
            299, 307, 308, 309
        ]),
        array([281]),
        array([271, 279, 282, 287, 295]),
        array([283]),
        array([284]),
        array([280, 285, 299, 309]),
        array([286]),
        array([282, 287]),
        array([288, 292]),
        array([289]),
        array([290]),
        array([291, 331]),
        array([288, 292]),
        array([293]),
        array([294]),
        array([72, 271, 274, 282, 295]),
        array([296]),
        array([297]),
        array([150, 164, 298, 300, 302]),
        array([
            10, 67, 72, 99, 120, 146, 168, 172, 213, 214, 215, 219, 221, 250, 258, 262, 274, 276,
            280, 285, 299, 302, 307, 308, 309, 327
        ]),
        array([150, 298, 300]),
        array([301]),
        array([298, 299, 302]),
        array([303]),
        array([304]),
        array([305]),
        array([306]),
        array([10, 99, 146, 168, 214, 215, 231, 274, 280, 299, 307, 308, 309]),
        array([10, 168, 221, 258, 280, 299, 307, 308, 309]),
        array([
            10, 73, 120, 146, 168, 207, 215, 231, 250, 258, 262, 265, 280, 285, 299, 307, 308, 309
        ]),
        array([310]),
        array([311]),
        array([312]),
        array([313]),
        array([131, 216, 235, 314]),
        array([315]),
        array([155, 226, 316, 318]),
        array([317]),
        array([316, 318]),
        array([7, 11, 25, 32, 41, 47, 319]),
        array([320]),
        array([114, 135, 321, 344]),
        array([322]),
        array([323]),
        array([165, 324]),
        array([135, 325, 344]),
        array([326]),
        array([10, 67, 99, 120, 168, 172, 214, 215, 219, 231, 299, 327]),
        array([328]),
        array([329]),
        array([330]),
        array([291, 331]),
        array([332]),
        array([333]),
        array([334]),
        array([335]),
        array([336]),
        array([337]),
        array([338]),
        array([339, 380]),
        array([340]),
        array([145, 148, 341, 373]),
        array([55, 118, 137, 139, 149, 342]),
        array([162, 343]),
        array([135, 148, 321, 325, 344]),
        array([345]),
        array([346]),
        array([347]),
        array([348]),
        array([349]),
        array([350]),
        array([351]),
        array([352]),
        array([353]),
        array([354]),
        array([355, 359]),
        array([356]),
        array([357]),
        array([358]),
        array([355, 359]),
        array([360]),
        array([361]),
        array([362]),
        array([363]),
        array([364]),
        array([365]),
        array([366]),
        array([367]),
        array([368]),
        array([369]),
        array([370]),
        array([183, 200, 371]),
        array([372]),
        array([148, 341, 373]),
        array([374]),
        array([375]),
        array([376]),
        array([377]),
        array([271, 378]),
        array([88, 379]),
        array([339, 380]),
        array([163, 381])
    ],
     {(237, ), (63, ), (356, ), (301, ), (127, ), (182, ), (365, ), (112, 210), (310, ), (339, 380),
      (291, 331), (374, ), (246, 257, 268), (155, 225, 226, 316, 318), (84, ), (29, ), (93, ),
      (102, ), (166, ), (230, ), (349, ), (114, 135, 145, 148, 321, 325, 341, 344, 373), (294, ),
      (239, ), (358, ), (184, ), (303, ), (248, ), (367, ), (312, ), (376, ), (77, ), (141, ),
      (86, ), (217, 222), (95, ), (40, ), (159, ), (278, ), (104, ), (223, ), (49, ), (232, ),
      (351, ), (177, ), (296, ), (131, 235, 216, 314), (360, ), (305, ), (369, ),
      (321, 325, 135, 145, 114, 148, 373, 341, 344), (6, ), (15, ), (79, ), (33, ), (152, ), (97, ),
      (42, ), (335, ), (106, ), (170, ), (289, ), (115, ), (234, ), (353, ), (179, ), (331, 291),
      (252, 255, 261), (243, ), (362, ), (50, 241), (8, ), (136, ), (254, 269, 273), (81, ), (26, ),
      (257, 246, 268), (264, ), (90, ), (209, ), (35, ), (328, ), (154, ), (337, ),
      (137, 139, 149, 342, 343, 161, 162, 118, 55, 56), (108, ), (227, ), (346, ),
      (163, 116, 157, 381), (236, ), (364, ), (1, ), (65, ), (54, 113, 175, 212, 218), (129, ),
      (74, ), (138, ), (83, ), (202, ), (28, ), (261, 252, 255), (266, ), (92, ), (211, ), (330, ),
      (156, ), (275, ), (101, ), (220, ), (284, ), (229, ), (348, ), (293, ), (357, ), (58, ),
      (122, ), (147, 165, 324), (186, ), (12, ), (131, 216, 235, 314), (76, ), (21, ), (140, ),
      (259, ), (85, ), (204, ), (30, ), (323, ), (94, ), (332, ), (158, ), (277, ),
      (10, 34, 59, 60, 67, 72, 73, 99, 120, 146, 150, 164, 168, 172, 188, 191, 203, 207, 208, 213,
       214, 215, 219, 221, 231, 247, 249, 250, 258, 262, 265, 270, 271, 274, 276, 279, 280, 282,
       285, 287, 295, 298, 299, 300, 302, 307, 308, 309, 327, 378), (241, 50), (286, ),
      (55, 56, 118, 137, 139, 149, 161, 162, 342, 343), (350, ), (225, 226, 155, 316, 318), (5, ),
      (124, ), (69, ), (14, ), (133, ), (143, 194), (78, ), (197, ), (142, ), (87, ), (206, ),
      (151, ), (334, ), (160, ), (224, ), (352, ), (53, ), (175, 113, 212, 54, 218), (117, ),
      (62, ), (181, ), (126, ), (245, ), (71, ), (190, ), (80, ), (144, ), (263, ), (89, ), (153, ),
      (272, ), (336, ), (281, ), (147, 324, 165), (345, ), (24, 31), (110, ), (174, ), (119, ),
      (238, ), (64, ), (9, ), (128, ), (194, 143), (366, ), (18, ), (311, ), (256, ), (375, ),
      (201, ), (82, ), (320, ), (321, 325, 135, 145, 114, 148, 341, 373, 344), (329, ),
      (0, 2, 3, 4, 7, 11, 13, 16, 17, 22, 23, 25, 32, 37, 38, 41, 44, 47, 319),
      (51, 183, 192, 193, 195, 196, 199, 200, 371), (338, ), (39, ), (103, ), (48, ), (167, ),
      (57, ), (176, ), (19, 20, 46), (121, ), (240, ), (66, ), (185, ), (304, ), (130, ), (75, ),
      (368, ), (313, ), (377, ), (322, ), (267, ),
      (258, 262, 265, 10, 270, 271, 274, 276, 279, 280, 282, 285, 287, 34, 295, 298, 299, 300, 302,
       307, 308, 309, 59, 60, 67, 327, 72, 73, 99, 120, 378, 146, 150, 164,
       168, 172, 188, 191, 203, 207, 208, 213, 214, 215, 219, 221, 231, 247, 249, 250),
      (273, 269, 254), (340, ), (96, ), (105, ), (288, 292), (169, ), (233, ), (178, ), (297, ),
      (123, ), (242, ), (361, ), (187, ), (68, ), (132, ), (251, ), (370, ), (306, ), (315, ),
      (260, ), (205, ), (333, ), (98, ), (43, ), (88, 379),
      (192, 193, 195, 196, 199, 200, 51, 371, 183), (107, ), (52, ), (171, ), (290, ), (61, ),
      (354, ), (180, ), (125, ), (244, ), (70, ), (363, ), (189, ), (134, ), (253, ), (372, ),
      (198, ), (317, ), (326, ), (355, 359), (27, ), (91, ), (116, 157, 163, 381), (36, ), (100, ),
      (109, 111), (45, ), (283, ), (228, ), (347, ), (173, )})
]


class TestUtilText(unittest.TestCase):
    def test_process_content(self):
        for input_test, expected_output in TEST_CASES.items():
            output = process_content(input_test)
            self.assertEqual(output, expected_output)

    def test_process_content_with_terms_mapping(self):
        for input_test, expected_output in TEST_CASES.items():
            output = process_content(input_test, terms_mapping=TERMS_MAPPING)
            self.assertEqual(output, expected_output)

    def test_remove_subsets(self):
        sets = [[0, 1, 3], [0, 1], [2], [0, 3], [4]]
        output = {(0, 1, 3), (2, ), (4, )}
        self.assertEquals(remove_subsets(sets), output)

    def test_remove_similar_sets(self):
        for test in TEST_SET_CASES:
            print(test[0], test[1])
            self.assertEquals(remove_similar_subsets(test[0]), test[1])
