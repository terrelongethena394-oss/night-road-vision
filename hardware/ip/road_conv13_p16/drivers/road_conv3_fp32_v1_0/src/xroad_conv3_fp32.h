// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2020.2 (64-bit)
// Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
// ==============================================================
#ifndef XROAD_CONV3_FP32_H
#define XROAD_CONV3_FP32_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xroad_conv3_fp32_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
    u16 DeviceId;
    u32 Control_BaseAddress;
} XRoad_conv3_fp32_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XRoad_conv3_fp32;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XRoad_conv3_fp32_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XRoad_conv3_fp32_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XRoad_conv3_fp32_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XRoad_conv3_fp32_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
int XRoad_conv3_fp32_Initialize(XRoad_conv3_fp32 *InstancePtr, u16 DeviceId);
XRoad_conv3_fp32_Config* XRoad_conv3_fp32_LookupConfig(u16 DeviceId);
int XRoad_conv3_fp32_CfgInitialize(XRoad_conv3_fp32 *InstancePtr, XRoad_conv3_fp32_Config *ConfigPtr);
#else
int XRoad_conv3_fp32_Initialize(XRoad_conv3_fp32 *InstancePtr, const char* InstanceName);
int XRoad_conv3_fp32_Release(XRoad_conv3_fp32 *InstancePtr);
#endif

void XRoad_conv3_fp32_Start(XRoad_conv3_fp32 *InstancePtr);
u32 XRoad_conv3_fp32_IsDone(XRoad_conv3_fp32 *InstancePtr);
u32 XRoad_conv3_fp32_IsIdle(XRoad_conv3_fp32 *InstancePtr);
u32 XRoad_conv3_fp32_IsReady(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_EnableAutoRestart(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_DisableAutoRestart(XRoad_conv3_fp32 *InstancePtr);
u32 XRoad_conv3_fp32_Get_return(XRoad_conv3_fp32 *InstancePtr);

void XRoad_conv3_fp32_Set_input_r(XRoad_conv3_fp32 *InstancePtr, u64 Data);
u64 XRoad_conv3_fp32_Get_input_r(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_weights_mem(XRoad_conv3_fp32 *InstancePtr, u64 Data);
u64 XRoad_conv3_fp32_Get_weights_mem(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_output_r(XRoad_conv3_fp32 *InstancePtr, u64 Data);
u64 XRoad_conv3_fp32_Get_output_r(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_height(XRoad_conv3_fp32 *InstancePtr, u32 Data);
u32 XRoad_conv3_fp32_Get_height(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_width(XRoad_conv3_fp32 *InstancePtr, u32 Data);
u32 XRoad_conv3_fp32_Get_width(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_ic4(XRoad_conv3_fp32 *InstancePtr, u32 Data);
u32 XRoad_conv3_fp32_Get_ic4(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_oc4(XRoad_conv3_fp32 *InstancePtr, u32 Data);
u32 XRoad_conv3_fp32_Get_oc4(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_stride(XRoad_conv3_fp32 *InstancePtr, u32 Data);
u32 XRoad_conv3_fp32_Get_stride(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_Set_kernel(XRoad_conv3_fp32 *InstancePtr, u32 Data);
u32 XRoad_conv3_fp32_Get_kernel(XRoad_conv3_fp32 *InstancePtr);

void XRoad_conv3_fp32_InterruptGlobalEnable(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_InterruptGlobalDisable(XRoad_conv3_fp32 *InstancePtr);
void XRoad_conv3_fp32_InterruptEnable(XRoad_conv3_fp32 *InstancePtr, u32 Mask);
void XRoad_conv3_fp32_InterruptDisable(XRoad_conv3_fp32 *InstancePtr, u32 Mask);
void XRoad_conv3_fp32_InterruptClear(XRoad_conv3_fp32 *InstancePtr, u32 Mask);
u32 XRoad_conv3_fp32_InterruptGetEnabled(XRoad_conv3_fp32 *InstancePtr);
u32 XRoad_conv3_fp32_InterruptGetStatus(XRoad_conv3_fp32 *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
