// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2020.2 (64-bit)
// Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
// ==============================================================
// control
// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read)
//        bit 7  - auto_restart (Read/Write)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0  - enable ap_done interrupt (Read/Write)
//        bit 1  - enable ap_ready interrupt (Read/Write)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0  - ap_done (COR/TOW)
//        bit 1  - ap_ready (COR/TOW)
//        others - reserved
// 0x10 : Data signal of ap_return
//        bit 31~0 - ap_return[31:0] (Read)
// 0x18 : Data signal of input_r
//        bit 31~0 - input_r[31:0] (Read/Write)
// 0x1c : Data signal of input_r
//        bit 31~0 - input_r[63:32] (Read/Write)
// 0x20 : reserved
// 0x24 : Data signal of weights_mem
//        bit 31~0 - weights_mem[31:0] (Read/Write)
// 0x28 : Data signal of weights_mem
//        bit 31~0 - weights_mem[63:32] (Read/Write)
// 0x2c : reserved
// 0x30 : Data signal of output_r
//        bit 31~0 - output_r[31:0] (Read/Write)
// 0x34 : Data signal of output_r
//        bit 31~0 - output_r[63:32] (Read/Write)
// 0x38 : reserved
// 0x3c : Data signal of height
//        bit 31~0 - height[31:0] (Read/Write)
// 0x40 : reserved
// 0x44 : Data signal of width
//        bit 31~0 - width[31:0] (Read/Write)
// 0x48 : reserved
// 0x4c : Data signal of ic4
//        bit 31~0 - ic4[31:0] (Read/Write)
// 0x50 : reserved
// 0x54 : Data signal of oc4
//        bit 31~0 - oc4[31:0] (Read/Write)
// 0x58 : reserved
// 0x5c : Data signal of stride
//        bit 31~0 - stride[31:0] (Read/Write)
// 0x60 : reserved
// 0x64 : Data signal of kernel
//        bit 31~0 - kernel[31:0] (Read/Write)
// 0x68 : reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL          0x00
#define XROAD_CONV3_FP32_CONTROL_ADDR_GIE              0x04
#define XROAD_CONV3_FP32_CONTROL_ADDR_IER              0x08
#define XROAD_CONV3_FP32_CONTROL_ADDR_ISR              0x0c
#define XROAD_CONV3_FP32_CONTROL_ADDR_AP_RETURN        0x10
#define XROAD_CONV3_FP32_CONTROL_BITS_AP_RETURN        32
#define XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA     0x18
#define XROAD_CONV3_FP32_CONTROL_BITS_INPUT_R_DATA     64
#define XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA 0x24
#define XROAD_CONV3_FP32_CONTROL_BITS_WEIGHTS_MEM_DATA 64
#define XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA    0x30
#define XROAD_CONV3_FP32_CONTROL_BITS_OUTPUT_R_DATA    64
#define XROAD_CONV3_FP32_CONTROL_ADDR_HEIGHT_DATA      0x3c
#define XROAD_CONV3_FP32_CONTROL_BITS_HEIGHT_DATA      32
#define XROAD_CONV3_FP32_CONTROL_ADDR_WIDTH_DATA       0x44
#define XROAD_CONV3_FP32_CONTROL_BITS_WIDTH_DATA       32
#define XROAD_CONV3_FP32_CONTROL_ADDR_IC4_DATA         0x4c
#define XROAD_CONV3_FP32_CONTROL_BITS_IC4_DATA         32
#define XROAD_CONV3_FP32_CONTROL_ADDR_OC4_DATA         0x54
#define XROAD_CONV3_FP32_CONTROL_BITS_OC4_DATA         32
#define XROAD_CONV3_FP32_CONTROL_ADDR_STRIDE_DATA      0x5c
#define XROAD_CONV3_FP32_CONTROL_BITS_STRIDE_DATA      32
#define XROAD_CONV3_FP32_CONTROL_ADDR_KERNEL_DATA      0x64
#define XROAD_CONV3_FP32_CONTROL_BITS_KERNEL_DATA      32

