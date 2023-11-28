#!/usr/bin/python3

import numpy

LLCP_FRAME_DATA_MSG_ID = 20

LLCP_STATUS_MSG_ID = 10
LLCP_STATUS_MSG_SIZE = 129

LLCP_TEMPERATURE_MSG_ID = 12
LLCP_TEMPERATURE_MSG_SIZE = 3

LLCP_FRAME_DATA_TERMINATOR_MSG_ID = 22
LLCP_FRAME_DATA_TERMINATOR_MSG_SIZE = 5

LLCP_FRAME_MEASUREMENT_FINISHED_MSG_ID = 24
LLCP_FRAME_MEASUREMENT_FINISHED_MSG_SIZE = 1

LLCP_ACK_MSG_ID = 40
LLCP_ACK_MSG_SIZE = 2

LLCP_MINIPIX_ERROR_MSG_ID = 90
LLCP_MINIPIX_ERROR_MSG_SIZE = 2

LLCP_MinipixErrors = ["MiniPIX: Frame measurement failed.",       "MiniPIX: Powerup failed.",
                      "MiniPIX: Powerup TPX3 reset sync error.",  "MiniPIX: Powerup TPX3 reset recv data error.",
                      "MiniPIX: Powerup TPX3 init resets error.", "MiniPIX: Powerup TPX3 init chip ID error.",
                      "MiniPIX: Powerup TPX3 init DACs error.",   "MiniPIX: Powerup TPX3 init PixCfg error.",
                      "MiniPIX: Powerup TPX3 init matrix error.", "MiniPIX: Invalid preset parameter."]

# LLCP_SET_CONFIGURATION_PRESET_REQ_MSG_ID =  80
# LLCP_SET_THRESHOLD_REQ_MSG_ID =  70
# LLCP_PWR_REQ_MSG_ID =  60
# LLCP_UPDATE_PIXEL_MASK_REQ_MSG_ID =  50
# LLCP_GET_FRAME_DATA_REQ_MSG_ID =  23
# LLCP_GET_STATUS_REQ_MSG_ID =  11
# LLCP_GET_TEMPERATURE_REQ_MSG_ID =  13
# LLCP_MEASURE_FRAME_REQ_MSG_ID =  21
