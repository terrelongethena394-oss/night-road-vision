#include "road_conv3_hls.h"
#include <vector>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <string>
#include <cmath>
#include <cstdint>
#include <cstring>
static unsigned bits(float f){unsigned u;std::memcpy(&u,&f,4);return u;}
static float value(unsigned u){float f;std::memcpy(&f,&u,4);return f;}
static bool load(const std::string &path,float *v,size_t n){std::ifstream f(path.c_str(),std::ios::binary);if(!f)return false;f.read(reinterpret_cast<char *>(v),n*4);return f.gcount()==(std::streamsize)(n*4)&&f.peek()==EOF;}
int main(int argc,char **argv){
 std::string mode=argc>1?argv[1]:"all",root=argc>2?argv[2]:".",list=root+"/"+(mode=="rtl"?"cases_rtl.txt":"cases_all.txt");
 std::ifstream names(list.c_str());if(!names)return 2;
 std::ofstream report((root+"/"+(mode=="rtl"?"tb_rtl.csv":"tb_csim.csv")).c_str());report<<"name,pe,outputs,max_abs,mae,bit_differences\n";
 std::vector<float> input(RC_MAX_INPUT,0.0f);
 std::vector<RoadWord> weights(RC_MAX_WEIGHT_WORDS,0),output(RC_MAX_OUTPUT_WORDS+1,0);
 std::string name;unsigned passed=0;RoadWord guard=0;
 for(int lane=0;lane<RC_PE;lane++)guard.range(lane*32+31,lane*32)=0x42f60000U;
 while(names>>name){
  std::string base=root+"/fixtures/"+name+"/";int h,w,ic,oc,s,k;
  std::ifstream meta((base+"shape.txt").c_str());meta>>h>>w>>ic>>oc>>s>>k;if(!meta)return 3;
  size_t ni=(size_t)h*w*ic,nw=(size_t)(oc/RC_PE)*(k*k*ic+1)*RC_PE,no=(size_t)((h+s-1)/s)*((w+s-1)/s)*oc;
  if(ni>RC_MAX_INPUT||nw/RC_PE>RC_MAX_WEIGHT_WORDS||no/RC_PE>RC_MAX_OUTPUT_WORDS)return 4;
  std::vector<float> packed(nw),expected(no);
  if(!load(base+"input.f32",input.data(),ni)||!load(base+"packed_p"+std::to_string(RC_PE)+".f32",packed.data(),nw)||!load(base+"expected.f32",expected.data(),no))return 5;
  for(size_t i=0;i<nw/RC_PE;i++){
   RoadWord a=0;for(int lane=0;lane<RC_PE;lane++)a.range(lane*32+31,lane*32)=bits(packed[i*RC_PE+lane]);weights[i]=a;
  }
  for(size_t i=0;i<=no/RC_PE;i++)output[i]=guard;
  int status=road_conv3_fp32(input.data(),weights.data(),output.data(),h,w,ic,oc,s,k);if(status){std::cerr<<"Unexpected status "<<name<<" "<<status<<"\n";return 6;}
  if(output[no/RC_PE]!=guard){std::cerr<<"Output overrun "<<name<<"\n";return 7;}
  double maximum=0,mae=0;size_t differences=0;
  std::vector<float> actual(no);
  for(size_t i=0;i<no;i++){
   unsigned u=output[i/RC_PE].range(32*(i%RC_PE)+31,32*(i%RC_PE)).to_uint();float v=value(u);actual[i]=v;double d=std::abs((double)v-expected[i]);
   if(!std::isfinite(v)||d>2e-5+2e-5*std::abs((double)expected[i])){std::cerr<<"NUMERIC_FAIL "<<name<<" index="<<i<<" expected="<<expected[i]<<" got="<<v<<" delta="<<d<<"\n";return 8;}
   if(d>maximum)maximum=d;mae+=d;if(u!=bits(expected[i]))differences++;
  }
  std::ofstream f((base+(mode=="rtl"?"rtl_p":"csim_p")+std::to_string(RC_PE)+".f32").c_str(),std::ios::binary);f.write(reinterpret_cast<const char *>(actual.data()),no*4);
  report<<name<<","<<RC_PE<<","<<no<<","<<std::setprecision(12)<<maximum<<","<<mae/no<<","<<differences<<"\n";report.flush();passed++;
  std::cout<<"ROAD_CONV3_CASE_PASS "<<name<<" PE="<<RC_PE<<" max_abs="<<maximum<<" bit_diff="<<differences<<std::endl;
 }
 // Reject unsupported dimensions/channels before touching any output.
 output[0]=guard;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),0,5,4,16,1,3)!=1||output[0]!=guard)return 9;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),161,5,4,16,1,3)!=1||output[0]!=guard)return 10;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,6,16,1,3)!=1||output[0]!=guard)return 11;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,4,16,3,3)!=1||output[0]!=guard)return 12;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),160,160,4,16,1,3)!=2||output[0]!=guard)return 13;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,4,16,1,2)!=1||output[0]!=guard)return 14;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,512,16,1,3)!=1||output[0]!=guard)return 15;
 if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,512,16,2,1)!=1||output[0]!=guard)return 16;
 std::cout<<"ROAD_CONV3_TESTBENCH_ALL_PASS mode="<<mode<<" cases="<<passed<<" PE="<<RC_PE<<" invalid_guards=8"<<std::endl;
 return 0;
}
