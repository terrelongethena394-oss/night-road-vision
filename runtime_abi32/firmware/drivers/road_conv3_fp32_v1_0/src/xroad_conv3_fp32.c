// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2020.2 (64-bit)
// Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
// ==============================================================
/***************************** Include Files *********************************/
#include "xroad_conv3_fp32.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XRoad_conv3_fp32_CfgInitialize(XRoad_conv3_fp32 *InstancePtr, XRoad_conv3_fp32_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XRoad_conv3_fp32_Start(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL) & 0x80;
    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XRoad_conv3_fp32_IsDone(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XRoad_conv3_fp32_IsIdle(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XRoad_conv3_fp32_IsReady(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XRoad_conv3_fp32_EnableAutoRestart(XRoad_conv3_fp32 *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XRoad_conv3_fp32_DisableAutoRestart(XRoad_conv3_fp32 *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_CTRL, 0);
}

u32 XRoad_conv3_fp32_Get_return(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_AP_RETURN);
    return Data;
}
void XRoad_conv3_fp32_Set_input_r(XRoad_conv3_fp32 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA, (u32)(Data));
    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA + 4, (u32)(Data >> 32));
}

u64 XRoad_conv3_fp32_Get_input_r(XRoad_conv3_fp32 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA);
    Data += (u64)XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_INPUT_R_DATA + 4) << 32;
    return Data;
}

void XRoad_conv3_fp32_Set_weights_mem(XRoad_conv3_fp32 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA, (u32)(Data));
    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA + 4, (u32)(Data >> 32));
}

u64 XRoad_conv3_fp32_Get_weights_mem(XRoad_conv3_fp32 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA);
    Data += (u64)XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_WEIGHTS_MEM_DATA + 4) << 32;
    return Data;
}

void XRoad_conv3_fp32_Set_output_r(XRoad_conv3_fp32 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA, (u32)(Data));
    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA + 4, (u32)(Data >> 32));
}

u64 XRoad_conv3_fp32_Get_output_r(XRoad_conv3_fp32 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA);
    Data += (u64)XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_OUTPUT_R_DATA + 4) << 32;
    return Data;
}

void XRoad_conv3_fp32_Set_height(XRoad_conv3_fp32 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_HEIGHT_DATA, Data);
}

u32 XRoad_conv3_fp32_Get_height(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_HEIGHT_DATA);
    return Data;
}

void XRoad_conv3_fp32_Set_width(XRoad_conv3_fp32 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_WIDTH_DATA, Data);
}

u32 XRoad_conv3_fp32_Get_width(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_WIDTH_DATA);
    return Data;
}

void XRoad_conv3_fp32_Set_ic4(XRoad_conv3_fp32 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IC4_DATA, Data);
}

u32 XRoad_conv3_fp32_Get_ic4(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IC4_DATA);
    return Data;
}

void XRoad_conv3_fp32_Set_oc4(XRoad_conv3_fp32 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_OC4_DATA, Data);
}

u32 XRoad_conv3_fp32_Get_oc4(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_OC4_DATA);
    return Data;
}

void XRoad_conv3_fp32_Set_stride(XRoad_conv3_fp32 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_STRIDE_DATA, Data);
}

u32 XRoad_conv3_fp32_Get_stride(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_STRIDE_DATA);
    return Data;
}

void XRoad_conv3_fp32_Set_kernel(XRoad_conv3_fp32 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_KERNEL_DATA, Data);
}

u32 XRoad_conv3_fp32_Get_kernel(XRoad_conv3_fp32 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_KERNEL_DATA);
    return Data;
}

void XRoad_conv3_fp32_InterruptGlobalEnable(XRoad_conv3_fp32 *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_GIE, 1);
}

void XRoad_conv3_fp32_InterruptGlobalDisable(XRoad_conv3_fp32 *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_GIE, 0);
}

void XRoad_conv3_fp32_InterruptEnable(XRoad_conv3_fp32 *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IER);
    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IER, Register | Mask);
}

void XRoad_conv3_fp32_InterruptDisable(XRoad_conv3_fp32 *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IER);
    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IER, Register & (~Mask));
}

void XRoad_conv3_fp32_InterruptClear(XRoad_conv3_fp32 *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XRoad_conv3_fp32_WriteReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_ISR, Mask);
}

u32 XRoad_conv3_fp32_InterruptGetEnabled(XRoad_conv3_fp32 *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_IER);
}

u32 XRoad_conv3_fp32_InterruptGetStatus(XRoad_conv3_fp32 *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XRoad_conv3_fp32_ReadReg(InstancePtr->Control_BaseAddress, XROAD_CONV3_FP32_CONTROL_ADDR_ISR);
}

