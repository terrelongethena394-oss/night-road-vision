// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2020.2 (64-bit)
// Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#include "xparameters.h"
#include "xroad_conv3_fp32.h"

extern XRoad_conv3_fp32_Config XRoad_conv3_fp32_ConfigTable[];

XRoad_conv3_fp32_Config *XRoad_conv3_fp32_LookupConfig(u16 DeviceId) {
	XRoad_conv3_fp32_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XROAD_CONV3_FP32_NUM_INSTANCES; Index++) {
		if (XRoad_conv3_fp32_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XRoad_conv3_fp32_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XRoad_conv3_fp32_Initialize(XRoad_conv3_fp32 *InstancePtr, u16 DeviceId) {
	XRoad_conv3_fp32_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XRoad_conv3_fp32_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XRoad_conv3_fp32_CfgInitialize(InstancePtr, ConfigPtr);
}

#endif

