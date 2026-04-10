_base_ = "mmdet::_base_/default_runtime.py"

model = dict(
    type="RetinaFace",
    backbone=dict(
        type="ResNetV1e",
        depth=0,
        block_cfg=dict(
            block="Bottleneck",
            stage_blocks=(17, 16, 2, 8),
            stage_planes=[56, 56, 144, 184],
        ),
        base_channels=56,
        num_stages=4,
        out_indices=(0, 1, 2, 3),
        norm_cfg=dict(type="BN", requires_grad=True),
        norm_eval=False,
        style="pytorch",
    ),
    neck=dict(
        type="PAFPN",
        in_channels=[224, 224, 576, 736],
        out_channels=128,
        start_level=1,
        add_extra_convs="on_output",
        num_outs=3,
    ),
    bbox_head=dict(
        type="RetinaFaceHead",
        num_classes=1,
        in_channels=128,
        use_ssh=False,
        stacked_convs=2,
        feat_channels=256,
        norm_cfg=dict(type="GN", num_groups=32, requires_grad=True),
        cls_reg_share=True,
        strides_share=True,
        scale_mode=2,
        anchor_generator=dict(
            type="AnchorGenerator",
            ratios=[1.0],
            scales=[1, 2],
            base_sizes=[16, 64, 256],
            strides=[8, 16, 32],
        ),
        loss_cls=dict(
            type="QualityFocalLoss", use_sigmoid=True, beta=2.0, loss_weight=1.0
        ),
        loss_dfl=False,
        reg_max=8,
        loss_bbox=dict(type="DIoULoss", loss_weight=2.0),
        use_kps=False,
        loss_kps=dict(type="SmoothL1Loss", beta=1.0 / 9.0, loss_weight=0.1),
    ),
)

test_cfg = dict(
    nms_pre=-1,
    min_bbox_size=0,
    score_thr=0.02,
    nms=dict(type="nms", iou_threshold=0.45),
    max_per_img=-1,
)
