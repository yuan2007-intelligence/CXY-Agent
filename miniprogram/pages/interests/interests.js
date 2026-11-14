const groups=require('../../data/interests.js')
Page({
 data:{interestGroups:[],selectedInterests:[]},
 onLoad(){this.setData({selectedInterests:[]});this.refresh()},
 refresh(){const selected=this.data.selectedInterests;this.setData({interestGroups:groups.map(g=>({id:g.id,name:g.name,options:g.options.map(o=>({id:o.id,label:o.label,selected:selected.indexOf(o.id)>=0}))}))})},
 toggleInterest(e){const id=e.currentTarget.dataset.id;const selected=this.data.selectedInterests;this.setData({selectedInterests:selected.indexOf(id)>=0?selected.filter(t=>t!==id):selected.concat(id)});this.refresh()},
 clearInterests(){this.setData({selectedInterests:[]});this.refresh()},
 confirmInterests(){try{wx.setStorageSync('interests',this.data.selectedInterests)}catch(e){wx.showToast({title:'保存失败，请重试',icon:'none'});return}getApp().globalData.chooseInterestsOnEntry=false;wx.redirectTo({url:'/pages/index/index'})}
})
